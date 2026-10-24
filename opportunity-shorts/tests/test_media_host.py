import sqlite3
from unittest.mock import Mock
import pytest
from shorts import media_host,buffer_api
from shorts.linkedin import SCHEMA

@pytest.fixture
def setup(monkeypatch):
    conn=sqlite3.connect(':memory:');conn.row_factory=sqlite3.Row;conn.executescript(SCHEMA);conn.executescript(media_host.SCHEMA)
    monkeypatch.setenv('MEDIA_HOST_URL','https://media.example.org');monkeypatch.setenv('MEDIA_WRITE_KEY','unit-test-only')
    cfg={'author':'buffer:page','image_cards':True,'buffer_channel_id':'page'}
    yield conn,cfg
    conn.close()


def add(conn,state='accepted'):
    conn.execute('INSERT INTO linkedin_posts(opportunity_id,author,status,commentary) VALUES (?,?,?,?)',('x','buffer:page',state,'text'))
    conn.execute('INSERT INTO linkedin_media VALUES (?,?,?,?,?,?,NULL,NULL,NULL)',('x','buffer:page','https://media.example.org/media/'+'a'*64+'.png','unused.png','hosted','2026-10-24T00:00:00Z'));conn.commit()


@pytest.mark.parametrize('state',['accepted','uncertain','publishing','pending','blocked','delivery_failed'])
def test_cleanup_holds_images_until_confirmed_posted(setup,state):
    conn,cfg=setup;add(conn,state);http=Mock()
    media_host.cleanup(conn,cfg,http)
    http.delete.assert_not_called()


def test_cleanup_deletes_after_confirmation_and_is_idempotent(setup):
    conn,cfg=setup;add(conn,'posted');http=Mock();http.delete.return_value.status_code=204
    media_host.cleanup(conn,cfg,http);media_host.cleanup(conn,cfg,http)
    http.delete.assert_called_once()
    assert conn.execute('SELECT state FROM linkedin_media').fetchone()[0]=='deleted'


def test_cleanup_failure_does_not_erase_publication_or_lose_retry(setup):
    conn,cfg=setup;add(conn,'posted');http=Mock();http.delete.side_effect=TimeoutError()
    media_host.cleanup(conn,cfg,http)
    assert conn.execute('SELECT status FROM linkedin_posts').fetchone()[0]=='posted'
    assert conn.execute('SELECT retry_after FROM linkedin_media').fetchone()[0]
    media_host.cleanup(conn,cfg,http);http.delete.assert_called_once()


def test_buffer_image_assets_and_cleanup_on_sent(setup,monkeypatch):
    conn,cfg=setup
    monkeypatch.setenv('BUFFER_API_KEY','unit-test-only')
    monkeypatch.setattr(buffer_api,'reserve_request',lambda:None)
    monkeypatch.setattr(media_host,'prepare',lambda *args:'https://media.example.org/media/image.png')
    cleanup=Mock();monkeypatch.setattr(media_host,'cleanup',cleanup)
    http=Mock();http.post.return_value.status_code=200
    http.post.return_value.json.return_value={'data':{'createPost':{'post':{'id':'post','channelId':'page','status':'sent'}}}}
    row={'id':'x','company':'Company','title':'Intern','location':'India','apply_url':'https://example.org/job'}
    assert buffer_api.publish(conn,row,cfg,http)=='posted'
    assert 'assets:[{image:{url:"https://media.example.org/media/image.png"}}]' in http.post.call_args.kwargs['json']['query']
    cleanup.assert_called_once_with(conn,cfg)


def test_upload_failure_retries_then_publishes_text_and_persists_fallback(setup,monkeypatch):
    conn,cfg=setup;monkeypatch.setenv('BUFFER_API_KEY','unit-test-only')
    prepare=Mock(side_effect=ValueError('Media unavailable'))
    monkeypatch.setattr(media_host,'prepare',prepare)
    monkeypatch.setattr(buffer_api,'reserve_request',lambda:None)
    http=Mock();http.post.return_value.status_code=200
    http.post.return_value.json.return_value={'data':{'createPost':{'post':{'id':'post','channelId':'page','status':'sent'}}}}
    row={'id':'x','company':'Company','title':'Intern','apply_url':'https://example.org/job'}
    assert buffer_api.publish(conn,row,cfg,http)=='posted'
    assert prepare.call_count==3
    assert 'assets:[]' in http.post.call_args.kwargs['json']['query']
    assert conn.execute('SELECT COUNT(*) FROM linkedin_media_fallback').fetchone()[0]==1
    assert media_host.prepare_optional(conn,row,cfg) is None
    assert prepare.call_count==3


def test_media_rejection_retries_text_only_without_duplicate_acceptance(setup,monkeypatch):
    conn,cfg=setup;monkeypatch.setenv('BUFFER_API_KEY','unit-test-only')
    monkeypatch.setattr(buffer_api,'reserve_request',lambda:None)
    monkeypatch.setattr(media_host,'prepare',lambda *a:'https://media.example.org/card.png')
    http=Mock();http.post.return_value.status_code=200
    http.post.return_value.json.side_effect=[{'data':{'createPost':{'__typename':'MutationError','message':'Invalid image asset'}}},{'data':{'createPost':{'post':{'id':'post','channelId':'page','status':'scheduled'}}}}]
    row={'id':'x','company':'Company','title':'Intern','apply_url':'https://example.org/job'}
    assert buffer_api.publish(conn,row,cfg,http)=='accepted'
    assert http.post.call_count==2
    assert 'assets:[]' in http.post.call_args.kwargs['json']['query']
    assert buffer_api.publish(conn,row,cfg,http)=='accepted'
    assert http.post.call_count==2


def test_ambiguous_image_submission_does_not_fallback_to_duplicate(setup,monkeypatch):
    conn,cfg=setup;monkeypatch.setenv('BUFFER_API_KEY','unit-test-only')
    monkeypatch.setattr(buffer_api,'reserve_request',lambda:None)
    monkeypatch.setattr(media_host,'prepare',lambda *a:'https://media.example.org/card.png')
    http=Mock();http.post.side_effect=TimeoutError()
    # Use the transport's actual requests exception classification.
    import requests
    http.post.side_effect=requests.Timeout()
    row={'id':'x','company':'Company','title':'Intern','apply_url':'https://example.org/job'}
    assert buffer_api.publish(conn,row,cfg,http)=='uncertain'
    assert buffer_api.publish(conn,row,cfg,http)=='uncertain'
    http.post.assert_called_once()


def test_missing_cleanup_configuration_never_blocks_posting(setup,monkeypatch):
    conn,cfg=setup
    monkeypatch.setattr(media_host,'cleanup',Mock(side_effect=ValueError('Missing credentials')))
    media_host.cleanup_optional(conn,cfg)
