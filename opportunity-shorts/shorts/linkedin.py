"""Independent company-page text-post outbox. Never retry ambiguous creates."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import os
import re
import time
from urllib.parse import urlsplit
import requests
from .priority import priority_key, compensation
from .editorial import application_tip
from .production import atomic_json

SCHEMA = """
CREATE TABLE IF NOT EXISTS linkedin_posts (
 opportunity_id TEXT NOT NULL, author TEXT NOT NULL, status TEXT NOT NULL,
 commentary TEXT NOT NULL, post_urn TEXT, attempted_at TEXT, retry_after TEXT,
 error TEXT, PRIMARY KEY(opportunity_id, author)
);
CREATE TABLE IF NOT EXISTS linkedin_attempts (
 opportunity_id TEXT NOT NULL, author TEXT NOT NULL, attempted_at TEXT NOT NULL
);
"""


def configuration(settings):
    cfg = dict(settings.get('linkedin', {}))
    cfg['author'] = os.getenv('LINKEDIN_ORGANIZATION_URN', cfg.get('author', ''))
    cfg['version'] = os.getenv('LINKEDIN_API_VERSION', cfg.get('version', '202609'))
    if cfg.get('provider') == 'buffer':
        cfg['buffer_channel_id'] = os.getenv('BUFFER_CHANNEL_ID', cfg.get('buffer_channel_id', ''))
        cfg['buffer_organization_id'] = os.getenv('BUFFER_ORGANIZATION_ID', cfg.get('buffer_organization_id', ''))
        cfg['author'] = 'buffer:' + cfg['buffer_channel_id']
    return cfg


def headers(cfg):
    if cfg.get('provider') == 'buffer':
        from .buffer_api import auth_headers
        return auth_headers()
    from collector.config import ROOT
    path = Path(os.getenv('LINKEDIN_TOKEN_FILE', 'secrets/linkedin_token.json'))
    if not path.is_absolute():
        path = ROOT / path
    if not re.fullmatch(r'urn:li:organization:\d+', cfg.get('author', '')):
        raise ValueError('Configure LINKEDIN_ORGANIZATION_URN for your company page')
    if not re.fullmatch(r'\d{6}', cfg.get('version', '')):
        raise ValueError('Configure a supported six-digit LINKEDIN_API_VERSION')
    if not path.exists():
        raise ValueError('LinkedIn authorization missing; run python -m shorts.linkedin auth')
    token = json.loads(path.read_text(encoding='utf-8'))
    if token.get('author') != cfg['author']:
        raise ValueError('Token is bound to a different company page; reconnect')
    if float(token.get('expires_at', 0)) <= time.time() + 60:
        if not token.get('refresh_token') or not os.getenv('LINKEDIN_CLIENT_SECRET') or not os.getenv('LINKEDIN_CLIENT_ID'):
            raise ValueError('LinkedIn token expired; reconnect with python -m shorts.linkedin auth')
        response = requests.post('https://www.linkedin.com/oauth/v2/accessToken', data={
            'grant_type': 'refresh_token', 'refresh_token': token['refresh_token'],
            'client_id': os.environ['LINKEDIN_CLIENT_ID'], 'client_secret': os.environ['LINKEDIN_CLIENT_SECRET']}, timeout=(10, 30))
        if response.status_code != 200:
            raise ValueError('LinkedIn token refresh rejected; reconnect')
        refreshed = response.json()
        if not refreshed.get('access_token') or not refreshed.get('expires_in'):
            raise ValueError('LinkedIn token refresh incomplete; reconnect')
        token.update(refreshed)
        token['expires_at'] = time.time() + int(refreshed['expires_in'])
        atomic_json(path, token)
    if not token.get('access_token'):
        raise ValueError('LinkedIn access token missing')
    return {'Authorization': 'Bearer ' + token['access_token'],
            'Linkedin-Version': cfg['version'], 'X-Restli-Protocol-Version': '2.0.0',
            'Content-Type': 'application/json'}


def commentary(row):
    row = dict(row)
    def clean(value, limit=250):
        # Escape LinkedIn commentary reserved markup so source text stays literal.
        value = ' '.join(str(value or '').split())[:limit]
        return re.sub(r'([\\|{}@\[\]()<>#*_~])', r'\\\1', value)
    url = row['apply_url']
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Application URL must be an HTTPS source URL')
    lines = [f"{clean(row['company'])} is hiring: {clean(row['title'])}", '',
             'Location: ' + clean(row.get('location') or 'Check the source listing'),
             'Stipend/pay: ' + clean(row.get('stipend_text') or 'Not disclosed')]
    from .trust import is_promoted
    if is_promoted(row):
        lines.insert(0, 'Promoted listing — paid collaboration')
    if row.get('deadline'):
        lines.append('Apply by: ' + clean(row['deadline']))
    lines += ['', clean(application_tip(row['title']), 450),
              '', 'Apply through the source listing:', url,
              '', 'Check the source for current eligibility and availability.',
              ' '.join(discovery_hashtags(row))]
    result = '\n'.join(lines)
    if len(result) > 3000:
        raise ValueError('LinkedIn commentary exceeds 3000 characters')
    return result


def discovery_hashtags(row):
    row = dict(row)
    role = row.get('title', '').lower()
    internship = row.get('opp_type') == 'internship' or 'intern' in role
    tags = ['#Hiring', '#Jobs', '#Internships' if internship else '#FresherJobs']
    topics = [('data science', '#DataScience'), ('machine learning', '#MachineLearning'),
              ('python', '#Python'), ('software', '#SoftwareEngineering'),
              ('web', '#WebDevelopment'), ('data', '#DataAnalytics'),
              ('marketing', '#DigitalMarketing'), ('design', '#DesignJobs'),
              ('finance', '#FinanceJobs')]
    match = next((tag for phrase, tag in topics if phrase in role), None)
    if match:
        tags.append(match)
    tags.append('#Unemployer')
    return tags


def publish_one(conn, row, cfg, http=requests):
    if cfg.get('provider') == 'buffer':
        from .buffer_api import publish
        return publish(conn, row, cfg, http)
    author = cfg['author']
    conn.executescript(SCHEMA)
    text = commentary(row)
    conn.execute('INSERT OR IGNORE INTO linkedin_posts(opportunity_id,author,status,commentary) VALUES (?,?,?,?)',
                 (row['id'], author, 'pending', text))
    conn.commit()
    saved = conn.execute('SELECT * FROM linkedin_posts WHERE opportunity_id=? AND author=?', (row['id'], author)).fetchone()
    if saved['status'] in ('posted', 'publishing', 'uncertain', 'blocked'):
        return saved['status']
    now = datetime.now(timezone.utc)
    if saved['retry_after'] and datetime.fromisoformat(saved['retry_after']) > now:
        return 'deferred'
    auth = headers(cfg)  # Preflight before the atomic claim.
    claim = conn.execute("UPDATE linkedin_posts SET status='publishing',commentary=?,attempted_at=?,error=NULL WHERE opportunity_id=? AND author=? AND status='pending'",
                         (text, now.isoformat(), row['id'], author))
    if claim.rowcount == 1:
        conn.execute('INSERT INTO linkedin_attempts VALUES (?,?,?)', (row['id'], author, now.isoformat()))
    conn.commit()
    if claim.rowcount != 1:
        return 'claimed'
    payload = {'author': author, 'commentary': text, 'visibility': 'PUBLIC',
               'distribution': {'feedDistribution': 'MAIN_FEED', 'targetEntities': [], 'thirdPartyDistributionChannels': []},
               'lifecycleState': 'PUBLISHED', 'isReshareDisabledByAuthor': False}
    state, urn, retry, error = 'uncertain', None, None, None
    try:
        response = http.post('https://api.linkedin.com/rest/posts', headers=auth, json=payload, timeout=(10, 30), allow_redirects=False)
        if response.status_code == 201:
            urn = response.headers.get('x-restli-id')
            if urn and re.fullmatch(r'urn:li:(share|ugcPost):\d+', urn):
                state = 'posted'
            else:
                error = 'Accepted response without a valid post ID; reconcile before retry'
        elif response.status_code == 429:
            state = 'pending'
            try:
                delay = int(response.headers.get('Retry-After', '3600'))
            except (ValueError, TypeError):
                delay = 3600
            delay = max(60, min(86400, delay))
            retry = (now + timedelta(seconds=delay)).isoformat()
            error = 'LinkedIn rate limit; deferred'
        elif response.status_code in (401, 403):
            state, error = 'blocked', 'LinkedIn authorization/page permission rejected; reconnect and verify access'
        elif 400 <= response.status_code < 500 and response.status_code != 408:
            state, error = 'blocked', f'LinkedIn rejected payload/version (HTTP {response.status_code}); inspect configuration'
        else:
            error = f'Ambiguous LinkedIn create result (HTTP {response.status_code}); reconciliation required'
    except requests.RequestException:
        error = 'Network failure during create; acceptance unknown, reconciliation required'
    except (ValueError, TypeError):
        error = 'Response could not be interpreted; reconciliation required'
    conn.execute('UPDATE linkedin_posts SET status=?,post_urn=?,retry_after=?,error=? WHERE opportunity_id=? AND author=?',
                 (state, urn, retry, error, row['id'], author))
    conn.commit()
    return state


def reconcile(conn, cfg, http=requests):
    if cfg.get('provider') == 'buffer':
        from .buffer_api import reconcile as buffer_reconcile
        return buffer_reconcile(conn, cfg)
    pending = conn.execute("SELECT * FROM linkedin_posts WHERE author=? AND status IN ('uncertain','publishing')", (cfg['author'],)).fetchall()
    if not pending:
        return
    auth = headers(cfg)
    auth['X-RestLi-Method'] = 'FINDER'
    found = []
    for start in range(0, 500, 100):
        response = http.get('https://api.linkedin.com/rest/posts', headers=auth,
            params={'q': 'author', 'author': cfg['author'], 'count': 100, 'start': start, 'sortBy': 'CREATED'}, timeout=(10, 30))
        if response.status_code != 200:
            return  # Hold uncertainty, including when read permission is unavailable.
        data = response.json()
        found.extend(data.get('elements', []))
        if not data.get('paging', {}).get('links'):
            break
    for item in pending:
        matches = [p for p in found if p.get('author') == cfg['author'] and p.get('commentary') == item['commentary'] and p.get('lifecycleState') == 'PUBLISHED']
        if len(matches) == 1 and re.fullmatch(r'urn:li:(share|ugcPost):\d+', matches[0].get('id', '')):
            conn.execute("UPDATE linkedin_posts SET status='posted',post_urn=?,error=NULL WHERE opportunity_id=? AND author=?", (matches[0]['id'], item['opportunity_id'], cfg['author']))
    conn.commit()


def run_cycle(pipeline):
    cfg = configuration(pipeline.settings)
    conn = pipeline.posts.conn
    conn.executescript(SCHEMA)
    if not cfg.get('enabled'):
        return {'state': 'disabled'}
    now = datetime.now(timezone.utc)
    interval = int(cfg.get('min_post_interval_minutes', 0))
    last = conn.execute('SELECT MAX(attempted_at) FROM linkedin_attempts WHERE author=?', (cfg['author'],)).fetchone()[0]
    if interval > 0 and last:
        next_post = datetime.fromisoformat(last) + timedelta(minutes=interval)
        if next_post > now:
            return {'state': 'spacing', 'next_post_at': next_post.isoformat(),
                'message': 'Spacing LinkedIn posts across the day'}
    headers(cfg)
    if cfg.get('provider') == 'buffer':
        from .buffer_api import check
        check(cfg)
    reconcile(conn, cfg)
    blocked = conn.execute("SELECT 1 FROM linkedin_posts WHERE author=? AND status='blocked' LIMIT 1", (cfg['author'],)).fetchone()
    if blocked:
        return {'state': 'blocked', 'message': 'Resolve rejected LinkedIn authorization/payload before resuming'}
    # LinkedIn text posts do not require a video, generation, or YouTube success.
    from .pipeline import IST
    rows = conn.execute("SELECT * FROM opportunities WHERE status IN ('new','approved','posted') AND is_open=1 AND (deadline IS NULL OR deadline>=?)",
        (now.astimezone(IST).date().isoformat(),)).fetchall()
    priority = pipeline.settings['automation'].get('priority', {})
    rows = sorted(rows, key=lambda r: priority_key(r, now.astimezone(IST).date(), int(priority.get('urgent_deadline_days', 3))))
    published = []
    accepted = []
    for row in rows:
        saved = conn.execute('SELECT status FROM linkedin_posts WHERE opportunity_id=? AND author=?', (row['id'], cfg['author'])).fetchone()
        if saved and saved['status'] != 'pending':
            continue  # Already posted/ambiguous items must not starve fresh candidates.
        if priority.get('skip_unpaid', True) and compensation(row['stipend_text'])[0] == 0:
            continue
        if not row['last_seen_at'] or datetime.fromisoformat(row['last_seen_at'].replace('Z', '+00:00')) < now - timedelta(hours=24):
            continue
        # Per-page daily attempt cap includes ambiguous/failed creates, not only successes.
        count = conn.execute('SELECT COUNT(*) FROM linkedin_attempts WHERE author=? AND attempted_at>=?', (cfg['author'], (now-timedelta(hours=24)).isoformat())).fetchone()[0]
        if count >= int(cfg.get('daily_limit', 10)):
            oldest = conn.execute('SELECT MIN(attempted_at) FROM linkedin_attempts WHERE author=? AND attempted_at>=?',
                (cfg['author'], (now-timedelta(hours=24)).isoformat())).fetchone()[0]
            return {'state': 'posting_limit', 'published': published, 'accepted': accepted,
                'attempts_24h': count, 'daily_limit': int(cfg.get('daily_limit', 10)),
                'next_retry_at': (datetime.fromisoformat(oldest)+timedelta(hours=24)).isoformat() if oldest else None,
                'message': 'Local LinkedIn daily cap reached; independent of YouTube'}
        state = publish_one(conn, row, cfg)
        if state == 'posted':
            published.append(row['id'])
        elif state == 'accepted':
            accepted.append(row['id'])
        if state in ('blocked', 'pending', 'uncertain') or (interval > 0 and state in ('posted', 'accepted')) or len(published) + len(accepted) >= int(cfg.get('max_posts_per_cycle', 3)):
            break
    return {'state': 'running', 'published': published, 'accepted': accepted}


def background(config_dir=None):
    from .pipeline import Pipeline
    from collector.config import load_settings
    health = Path(load_settings(config_dir)['db_path']).parent / 'linkedin-health.json'
    while True:
        p = None
        try:
            p = Pipeline(config_dir)
            result = run_cycle(p)
        except ValueError as exc:
            result = {'state': 'configuration_error', 'message': str(exc)}
        except Exception:
            result = {'state': 'error', 'message': 'LinkedIn configuration, token, or API unavailable; YouTube continues. Run LinkedIn status/check.'}
        finally:
            if p is not None:
                p.close()
        atomic_json(health, dict(result, checked_at=datetime.now(timezone.utc).isoformat()))
        time.sleep(15)


def main():
    import argparse
    from .pipeline import Pipeline
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['auth', 'check', 'status', 'preview', 'run', 'resume'])
    parser.add_argument('id', nargs='?')
    args = parser.parse_args()
    p = Pipeline()
    try:
        cfg = configuration(p.settings)
        p.posts.conn.executescript(SCHEMA)
        if args.command == 'auth':
            from .linkedin_auth import authorize
            authorize(cfg)
        elif args.command == 'check':
            if cfg.get('provider') == 'buffer':
                from .buffer_api import check
                print(json.dumps(check(cfg)))
                return
            auth = headers(cfg)
            auth['X-RestLi-Method'] = 'FINDER'
            response = requests.get('https://api.linkedin.com/rest/posts', headers=auth,
                params={'q': 'author', 'author': cfg['author'], 'count': 1}, timeout=(10, 30))
            if response.status_code != 200:
                raise ValueError(f'LinkedIn page read/access check failed (HTTP {response.status_code}); check approved scopes/page role/version')
            print('Company-page read access verified. Write access requires a successful initial publish.')
        elif args.command == 'preview':
            row = p.db.get(args.id or '')
            if not row:
                raise ValueError('Provide an exact opportunity ID')
            print(commentary(row))
        elif args.command == 'run':
            print(json.dumps(run_cycle(p)))
        elif args.command == 'resume':
            headers(cfg)
            p.posts.conn.execute("UPDATE linkedin_posts SET status='pending',retry_after=NULL WHERE author=? AND status='blocked'", (cfg['author'],))
            p.posts.conn.commit()
            print('Explicitly rejected posts resumed; uncertain creates remain held')
        else:
            print(json.dumps({'enabled': cfg.get('enabled', False), 'author': cfg.get('author'), 'posts': [dict(r) for r in p.posts.conn.execute('SELECT opportunity_id,status,post_urn,retry_after,error FROM linkedin_posts')]}))
    finally:
        p.close()


if __name__ == '__main__':
    main()
