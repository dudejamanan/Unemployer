import sqlite3
from datetime import datetime, timezone
from unittest.mock import Mock
import pytest
import requests
from shorts import linkedin


@pytest.fixture
def conn():
    c = sqlite3.connect(':memory:')
    c.row_factory = sqlite3.Row
    c.executescript(linkedin.SCHEMA)
    yield c
    c.close()


@pytest.fixture
def row():
    return dict(id='opportunity', company='Example', title='Python Intern',
                location='India', stipend_text='INR 25000/month',
                apply_url='https://example.com/apply', deadline='2026-12-31')


@pytest.fixture
def cfg(monkeypatch):
    monkeypatch.setattr(linkedin, 'headers', lambda cfg: {'Authorization': 'Bearer test'})
    return dict(author='urn:li:organization:123', version='202609')


def test_content_uses_source_facts_and_no_invented_pay(row):
    text = linkedin.commentary(row)
    assert 'INR 25000/month' in text
    assert row['apply_url'] in text
    assert 'Application tip:' in text
    row['stipend_text'] = ''
    assert 'Not disclosed' in linkedin.commentary(row)
    row['apply_url'] = 'javascript:alert(1)'
    with pytest.raises(ValueError):
        linkedin.commentary(row)


def test_success_is_idempotent(conn, row, cfg):
    http = Mock()
    http.post.return_value.status_code = 201
    http.post.return_value.headers = {'x-restli-id': 'urn:li:share:1234'}
    assert linkedin.publish_one(conn, row, cfg, http) == 'posted'
    assert linkedin.publish_one(conn, row, cfg, http) == 'posted'
    http.post.assert_called_once()
    assert http.post.call_args.kwargs['json']['author'] == cfg['author']


@pytest.mark.parametrize('code', [401, 403, 400, 426])
def test_definitive_rejection_blocks_without_repeat(conn, row, cfg, code):
    http = Mock()
    http.post.return_value.status_code = code
    assert linkedin.publish_one(conn, row, cfg, http) == 'blocked'
    assert linkedin.publish_one(conn, row, cfg, http) == 'blocked'
    http.post.assert_called_once()


def test_rate_limit_has_cooldown(conn, row, cfg):
    http = Mock()
    http.post.return_value.status_code = 429
    http.post.return_value.headers = {'Retry-After': '120'}
    assert linkedin.publish_one(conn, row, cfg, http) == 'pending'
    assert linkedin.publish_one(conn, row, cfg, http) == 'deferred'
    http.post.assert_called_once()
    assert conn.execute('SELECT COUNT(*) FROM linkedin_attempts').fetchone()[0] == 1


@pytest.mark.parametrize('code', [500, 408, 201])
def test_ambiguous_acceptance_is_not_retried(conn, row, cfg, code):
    http = Mock()
    http.post.return_value.status_code = code
    http.post.return_value.headers = {}
    assert linkedin.publish_one(conn, row, cfg, http) == 'uncertain'
    assert linkedin.publish_one(conn, row, cfg, http) == 'uncertain'
    http.post.assert_called_once()


def test_lost_response_reconciles_by_exact_author_and_content(conn, row, cfg):
    http = Mock()
    http.post.side_effect = requests.Timeout()
    assert linkedin.publish_one(conn, row, cfg, http) == 'uncertain'
    http.get.return_value.status_code = 200
    http.get.return_value.json.return_value = dict(elements=[dict(
        author=cfg['author'], commentary=linkedin.commentary(row),
        lifecycleState='PUBLISHED', id='urn:li:share:5678')], paging={})
    linkedin.reconcile(conn, cfg, http)
    assert linkedin.publish_one(conn, row, cfg, http) == 'posted'
    http.post.assert_called_once()


def test_multiple_matches_remain_held(conn, row, cfg):
    http = Mock()
    http.post.side_effect = requests.Timeout()
    linkedin.publish_one(conn, row, cfg, http)
    match = dict(author=cfg['author'], commentary=linkedin.commentary(row),
                 lifecycleState='PUBLISHED', id='urn:li:share:5678')
    http.get.return_value.status_code = 200
    http.get.return_value.json.return_value = dict(elements=[match, match], paging={})
    linkedin.reconcile(conn, cfg, http)
    assert conn.execute('SELECT status FROM linkedin_posts').fetchone()[0] == 'uncertain'


def test_disabled_requires_no_credentials(conn):
    p = Mock()
    p.posts.conn = conn
    p.settings = {'linkedin': {'enabled': False}}
    assert linkedin.run_cycle(p) == {'state': 'disabled'}


def test_run_cycle_does_not_starve_new_posts_behind_posted_or_uncertain(conn, cfg, monkeypatch):
    conn.executescript("""
      CREATE TABLE opportunities(id TEXT PRIMARY KEY,company TEXT,title TEXT,location TEXT,
       stipend_text TEXT,apply_url TEXT,deadline TEXT,last_seen_at TEXT,status TEXT,is_open INT,description TEXT);
      CREATE TABLE posts(opportunity_id TEXT,status TEXT);
    """)
    now = datetime.now(timezone.utc).isoformat()
    for id, pay, status in [('already', 55000, 'posted'), ('held', 45000, 'uncertain'), ('fresh', 25000, None)]:
        conn.execute('INSERT INTO opportunities VALUES (?,?,?,?,?,?,?,?,?,?,?)', (id,'Example',id,'India',f'INR {pay}/month','https://example.com/'+id,None,now,'new',1,''))
        conn.execute('INSERT INTO posts VALUES (?,?)', (id,'ready'))
        if status:
            conn.execute('INSERT INTO linkedin_posts(opportunity_id,author,status,commentary) VALUES (?,?,?,?)', (id,cfg['author'],status,'test'))
    conn.commit()
    p=Mock(); p.posts.conn=conn
    p.settings={'linkedin': dict(cfg,enabled=True), 'automation': {}}
    monkeypatch.setattr(linkedin,'reconcile',lambda *args: None)
    publish=Mock(return_value='posted')
    monkeypatch.setattr(linkedin,'publish_one',publish)
    result=linkedin.run_cycle(p)
    assert result['published']==['fresh']
    assert publish.call_count==1


def test_promoted_disclosure(row):
    row['description']='Sponsored: internship promotion'
    assert linkedin.commentary(row).startswith('Promoted listing')
