import sqlite3
from unittest.mock import Mock
import pytest
import requests
from shorts import buffer_api
from shorts.linkedin import SCHEMA

@pytest.fixture
def conn():
    c=sqlite3.connect(':memory:'); c.row_factory=sqlite3.Row; c.executescript(SCHEMA)
    yield c
    c.close()

@pytest.fixture
def row():
    return dict(id='x',company='Company',title='Data Intern',location='India',stipend_text='INR 25000/month',apply_url='https://example.com/job')

@pytest.fixture
def cfg(monkeypatch):
    monkeypatch.setenv('BUFFER_API_KEY','test-secret')
    monkeypatch.setattr(buffer_api,'reserve_request',lambda: None)
    return dict(author='buffer:channel',buffer_channel_id='channel',buffer_organization_id='org')

def test_buffer_acceptance_is_not_publication(conn,row,cfg):
    http=Mock(); http.post.return_value.status_code=200
    http.post.return_value.json.return_value={'data':{'createPost':{'post':{'id':'post1','channelId':'channel','status':'scheduled'}}}}
    assert buffer_api.publish(conn,row,cfg,http)=='accepted'
    assert buffer_api.publish(conn,row,cfg,http)=='accepted'
    http.post.assert_called_once()
    document=http.post.call_args.kwargs['json']['query']
    assert 'mode:shareNow' in document and 'needsApproval:false' in document
    assert 'test-secret' not in document

@pytest.mark.parametrize('code',[500,408])
def test_buffer_uncertain_is_held(conn,row,cfg,code):
    http=Mock(); http.post.return_value.status_code=code
    assert buffer_api.publish(conn,row,cfg,http)=='uncertain'
    assert buffer_api.publish(conn,row,cfg,http)=='uncertain'
    http.post.assert_called_once()

def test_buffer_rate_limit_defers(conn,row,cfg):
    http=Mock(); http.post.return_value.status_code=429
    http.post.return_value.headers={'Retry-After':'120'}
    assert buffer_api.publish(conn,row,cfg,http)=='pending'
    assert buffer_api.publish(conn,row,cfg,http)=='deferred'
    http.post.assert_called_once()

def test_buffer_reconciles_delivered_and_does_not_duplicate(conn,row,cfg,monkeypatch):
    http=Mock(); http.post.side_effect=requests.Timeout()
    assert buffer_api.publish(conn,row,cfg,http)=='uncertain'
    saved=conn.execute('SELECT commentary FROM linkedin_posts').fetchone()[0]
    monkeypatch.setattr(buffer_api,'query',lambda *a,**k: {'posts':{'edges':[{'node':{'id':'post1','channelId':'channel','text':saved,'status':'sent','externalLink':'https://linkedin.com/post'}}]}})
    buffer_api.reconcile(conn,cfg)
    assert buffer_api.publish(conn,row,cfg,http)=='posted'
    http.post.assert_called_once()

def test_company_page_identity_check(cfg,monkeypatch):
    monkeypatch.setattr(buffer_api,'channels',lambda *a: [dict(id='channel',service='linkedin',type='profile',isDisconnected=False,isLocked=False,isQueuePaused=False)])
    with pytest.raises(ValueError,match='company page'):
        buffer_api.check(cfg)


def test_unresolved_posts_do_not_poll_every_cycle(conn,row,cfg,monkeypatch):
    http=Mock(); http.post.side_effect=requests.Timeout()
    assert buffer_api.publish(conn,row,cfg,http)=='uncertain'
    read=Mock(return_value={'posts':{'edges':[]}})
    monkeypatch.setattr(buffer_api,'query',read)
    buffer_api.reconcile(conn,cfg)
    buffer_api.reconcile(conn,cfg)
    read.assert_called_once()
    assert conn.execute('SELECT status FROM linkedin_posts').fetchone()[0]=='uncertain'
