"""Buffer GraphQL transport and durable LinkedIn delivery adapter."""
import json
import os
import re
import time
import sqlite3
from datetime import datetime, timedelta, timezone
import requests

POST_FIELDS = 'id text channelId status externalLink'
_channel_cache = {}


def reserve_request():
    """Keep automatic usage below the Free plan's rolling API budgets."""
    from collector.config import load_settings
    with sqlite3.connect(load_settings()['db_path'], timeout=30) as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS buffer_requests(attempted_at TEXT NOT NULL)')
        conn.execute('BEGIN IMMEDIATE')
        now = datetime.now(timezone.utc)
        for days, limit in ((1, 80), (30, 2600)):
            count = conn.execute('SELECT COUNT(*) FROM buffer_requests WHERE attempted_at>=?', ((now-timedelta(days=days)).isoformat(),)).fetchone()[0]
            if count >= limit:
                raise BufferError('Buffer local API budget exhausted; will resume as requests leave the rolling window', 429)
        conn.execute('INSERT INTO buffer_requests VALUES (?)', (now.isoformat(),))
        conn.execute('DELETE FROM buffer_requests WHERE attempted_at<?', ((now-timedelta(days=31)).isoformat(),))


class BufferError(ValueError):
    def __init__(self, message, status=0):
        super().__init__(message)
        self.status = status


def auth_headers():
    key = os.getenv('BUFFER_API_KEY', '').strip()
    if not key:
        raise BufferError('BUFFER_API_KEY is missing from the local .env')
    return {'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'}


def query(document, http=requests):
    reserve_request()
    response = http.post('https://api.buffer.com', headers=auth_headers(), json={'query': document},
                         timeout=(10, 30), allow_redirects=False)
    if response.status_code != 200:
        raise BufferError(f'Buffer API returned HTTP {response.status_code}', response.status_code)
    data = response.json()
    if data.get('errors'):
        # Do not include arbitrary remote messages/credentials in operational logs.
        raise BufferError('Buffer GraphQL request rejected; check schema, access and plan limits')
    return data.get('data') or {}


def channels(organization):
    return query('query { channels(input:{organizationId:'+json.dumps(organization)+'}) { id name service type externalLink isDisconnected isLocked isQueuePaused } }').get('channels', [])


def check(cfg):
    cache_key = (cfg['buffer_organization_id'], cfg['buffer_channel_id'])
    cached = _channel_cache.get(cache_key)
    if cached and time.monotonic() - cached[0] < 3600:
        return cached[1]
    matches = [c for c in channels(cfg['buffer_organization_id']) if c['id'] == cfg['buffer_channel_id']]
    if len(matches) != 1:
        raise BufferError('Configured Buffer channel is not accessible in this organization')
    channel = matches[0]
    if channel['service'] != 'linkedin' or channel['type'] != 'page':
        raise BufferError('Buffer target must be a LinkedIn company page')
    if channel['isDisconnected'] or channel['isLocked'] or channel['isQueuePaused']:
        raise BufferError('Buffer LinkedIn page is disconnected, locked or paused; reconnect/unpause in Buffer')
    limits = query('query { dailyPostingLimits(input:{channelIds:['+json.dumps(cfg['buffer_channel_id'])+']}) { channelId isAtLimit limit sent scheduled } }').get('dailyPostingLimits', [])
    if any(item.get('isAtLimit') for item in limits if item.get('channelId') == cfg['buffer_channel_id']):
        raise BufferError('Buffer company-page daily posting limit reached; retry after allowance resets')
    _channel_cache[cache_key] = (time.monotonic(), channel)
    return channel


def publish(conn, row, cfg, http=requests):
    from .linkedin import SCHEMA, commentary
    author = cfg['author']
    conn.executescript(SCHEMA)
    text = commentary(row)
    # Buffer plain text must not receive LinkedIn API rich-text escaping.
    text = re.sub(r'\\([\\|{}@\[\]()<>#*_~])', r'\1', text)
    conn.execute('INSERT OR IGNORE INTO linkedin_posts(opportunity_id,author,status,commentary) VALUES (?,?,?,?)',
                 (row['id'], author, 'pending', text))
    conn.commit()
    saved = conn.execute('SELECT * FROM linkedin_posts WHERE opportunity_id=? AND author=?', (row['id'], author)).fetchone()
    if saved['status'] != 'pending':
        return saved['status']
    now = datetime.now(timezone.utc)
    if saved['retry_after'] and datetime.fromisoformat(saved['retry_after']) > now:
        return 'deferred'
    headers = auth_headers()
    reserve_request()  # Exhausted request budgets must not claim a create as uncertain.
    claim = conn.execute("UPDATE linkedin_posts SET status='publishing',commentary=?,attempted_at=?,error=NULL WHERE opportunity_id=? AND author=? AND status='pending'",
                         (text, now.isoformat(), row['id'], author))
    if claim.rowcount == 1:
        conn.execute('INSERT INTO linkedin_attempts VALUES (?,?,?)', (row['id'], author, now.isoformat()))
    conn.commit()
    if claim.rowcount != 1:
        return 'claimed'
    document = 'mutation { createPost(input:{channelId:'+json.dumps(cfg['buffer_channel_id'])+',text:'+json.dumps(text)+',schedulingType:automatic,mode:shareNow,assets:[],needsApproval:false}) { __typename ... on PostActionSuccess { post { '+POST_FIELDS+' } } ... on MutationError { message } } }'
    state, id, retry, error = 'uncertain', None, None, None
    try:
        response = http.post('https://api.buffer.com', headers=headers, json={'query': document}, timeout=(10,30), allow_redirects=False)
        if response.status_code == 429:
            state, error = 'pending', 'Buffer rate limit; retry after cooldown'
            try:
                seconds = int(response.headers.get('Retry-After', '3600'))
            except (ValueError, TypeError):
                seconds = 3600
            retry = (now+timedelta(seconds=max(60,min(86400,seconds)))).isoformat()
        elif response.status_code in (400,401,403):
            state, error = 'blocked', f'Buffer rejected request (HTTP {response.status_code}); check account/configuration'
        elif response.status_code == 200:
            data = response.json()
            result = (data.get('data') or {}).get('createPost') or {}
            post = result.get('post') or {}
            if post.get('id') and post.get('channelId') == cfg['buffer_channel_id']:
                id = post['id']
                state = 'posted' if post.get('status') == 'sent' else 'delivery_failed' if post.get('status') == 'error' else 'accepted'
            elif result.get('__typename') == 'MutationError' and not data.get('errors'):
                state, error = 'blocked', 'Buffer rejected post; inspect Buffer dashboard and account limits'
            else:
                error = 'Buffer create response ambiguous; reconcile before retry'
        else:
            error = f'Buffer create outcome uncertain (HTTP {response.status_code})'
    except (requests.RequestException, ValueError, TypeError):
        error = 'Buffer create response lost/unreadable; reconcile before retry'
    conn.execute('UPDATE linkedin_posts SET status=?,post_urn=?,retry_after=?,error=? WHERE opportunity_id=? AND author=?',
                 (state,id,retry,error,row['id'],author))
    conn.commit()
    return state


def reconcile(conn, cfg):
    rows = conn.execute("SELECT * FROM linkedin_posts WHERE author=? AND status IN ('publishing','uncertain','accepted')", (cfg['author'],)).fetchall()
    if not rows:
        return
    conn.execute('CREATE TABLE IF NOT EXISTS buffer_reconcile_checks(author TEXT PRIMARY KEY, next_check_at TEXT NOT NULL)')
    now = datetime.now(timezone.utc)
    previous = conn.execute('SELECT next_check_at FROM buffer_reconcile_checks WHERE author=?', (cfg['author'],)).fetchone()
    if previous and datetime.fromisoformat(previous[0]) > now:
        return
    conn.execute('INSERT OR REPLACE INTO buffer_reconcile_checks VALUES (?,?)',
        (cfg['author'], (now + timedelta(hours=1)).isoformat()))
    conn.commit()  # Failed lookups also back off; avoid draining the API budget.
    # Bounded author-channel scan includes scheduled, sent and failed Buffer posts.
    data = query('query { posts(first:100,input:{organizationId:'+json.dumps(cfg['buffer_organization_id'])+',filter:{channelIds:['+json.dumps(cfg['buffer_channel_id'])+']},sort:[{field:createdAt,direction:desc}]}) { edges { node { '+POST_FIELDS+' } } } }')
    found = [e['node'] for e in (data.get('posts') or {}).get('edges', [])]
    for row in rows:
        matches = [p for p in found if p['channelId']==cfg['buffer_channel_id'] and (p['id']==row['post_urn'] if row['post_urn'] else p['text']==row['commentary'])]
        if len(matches) != 1:
            continue  # Missing/ambiguous does not justify creating again.
        post = matches[0]
        state = 'posted' if post['status']=='sent' else 'delivery_failed' if post['status']=='error' else 'accepted'
        conn.execute('UPDATE linkedin_posts SET status=?,post_urn=?,error=? WHERE opportunity_id=? AND author=?',
                     (state,post['id'],'Delivery failed; inspect Buffer, do not recreate blindly' if state=='delivery_failed' else None,row['opportunity_id'],cfg['author']))
    conn.commit()
