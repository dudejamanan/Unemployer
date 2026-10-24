from __future__ import annotations
import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock
import pytest

from collector.models import Opportunity
from collector.normalize import enrich
from shorts.pipeline import Pipeline, IST
from shorts.script_gen import _template_fallback
from shorts.validate_script import validate_script
from shorts.settings import load_shorts_settings
from shorts.scheduler import schedule, run_daily
from shorts.tts import TTSResult


@pytest.fixture
def pipeline(tmp_path, monkeypatch):
    monkeypatch.setenv('OPP_DB_PATH', str(tmp_path / 'opportunities.db'))
    config = tmp_path / 'config'
    config.mkdir()
    (config / 'shorts.yaml').write_text(f'llm:\n  provider: template\npaths:\n  output_dir: {tmp_path.as_posix()}/out\n')
    p = Pipeline(config)
    opp = Opportunity(source='manual', board='manual', external_id='test',
        title='Software Engineering Intern', company='Example Corp',
        location='Bengaluru, India', apply_url='https://example.com/careers/test',
        description='Students can apply through the official careers page.',
        stipend_text='Rs 25,000 per month', batch_years=[2027, 2028], opp_type='internship')
    enrich(opp)
    p.db.upsert(opp)
    p.test_id = opp.id
    p.config_dir = config
    yield p
    p.close()


def mock_media(monkeypatch):
    tts = Mock(return_value=TTSResult('voice.mp3', 25, [{'word': 'hello', 'start': 0, 'end': 1}]))
    async def voice(*args, **kwargs):
        return tts(*args, **kwargs)
    monkeypatch.setattr('shorts.pipeline.generate_tts', voice)
    monkeypatch.setattr('shorts.pipeline.render_all_scenes', lambda *args: [Path('scene.png')]*4)
    def assembly(scenes, audio, output, *args, **kwargs):
        output.write_bytes(b'video fixture')
        return output
    monkeypatch.setattr('shorts.pipeline.assemble_with_captions', assembly)
    return tts


def test_complete_review_export_upload_and_rerun(pipeline, monkeypatch):
    p = pipeline
    tts = mock_media(monkeypatch)
    post = p.build(p.test_id)
    assert post.status == 'generated'
    p.build(p.test_id)
    assert tts.call_count == 1
    with pytest.raises(ValueError, match='approval'):
        p.upload(p.test_id)
    p.db.set_status(p.test_id, 'approved')
    with pytest.raises(ValueError, match='video approval'):
        p.upload(p.test_id)
    p.approve_video(p.test_id)
    folder = p.upload(p.test_id, manual_export=True)
    assert (folder / 'video.mp4').exists()
    assert (folder / 'description.txt').read_text().startswith('https://example.com/careers/test')
    assert p.db.get(p.test_id)['status'] == 'approved'
    upload = Mock(return_value='abcdefghijk')
    monkeypatch.setattr('shorts.upload.upload_video', upload)
    assert p.upload(p.test_id) == 'abcdefghijk'
    assert p.db.get(p.test_id)['status'] == 'posted'
    assert p.upload(p.test_id) == 'abcdefghijk'
    assert upload.call_count == 1


def test_uncertain_upload_is_locked(pipeline, monkeypatch):
    p = pipeline
    mock_media(monkeypatch)
    p.build(p.test_id)
    p.db.set_status(p.test_id, 'approved')
    p.approve_video(p.test_id)
    monkeypatch.setattr('shorts.upload.upload_video', Mock(side_effect=TimeoutError('lost response')))
    with pytest.raises(TimeoutError):
        p.upload(p.test_id)
    assert p.posts.get(p.test_id).status == 'uploading'
    assert p.db.get(p.test_id)['status'] == 'approved'
    with pytest.raises(ValueError):
        p.upload(p.test_id)


def test_rejected_upload_is_deferred_without_uncertain_lock(pipeline, monkeypatch):
    import httplib2
    from googleapiclient.errors import HttpError
    p = pipeline
    mock_media(monkeypatch)
    p.build(p.test_id)
    p.db.set_status(p.test_id, 'approved')
    p.approve_video(p.test_id)
    error = HttpError(httplib2.Response({'status': '403'}), b'{"error":{"errors":[{"reason":"quotaExceeded"}],"message":"quota"}}')
    monkeypatch.setattr('shorts.upload.upload_video', Mock(side_effect=error))
    with pytest.raises(HttpError):
        p.upload(p.test_id)
    assert p.posts.get(p.test_id).status == 'ready'
    retry = p.posts.conn.execute('SELECT retry_after FROM upload_retries WHERE opportunity_id=?', (p.test_id,)).fetchone()
    assert datetime.fromisoformat(retry[0]).date() > datetime.now(IST).date()


def test_channel_upload_limit_retries_within_an_hour(pipeline, monkeypatch):
    import httplib2
    from googleapiclient.errors import HttpError
    p = pipeline
    mock_media(monkeypatch)
    p.build(p.test_id)
    p.db.set_status(p.test_id, 'approved')
    p.approve_video(p.test_id)
    error = HttpError(httplib2.Response({'status': '400'}), b'{"error":{"errors":[{"reason":"uploadLimitExceeded"}]}}')
    monkeypatch.setattr('shorts.upload.upload_video', Mock(side_effect=error))
    before = datetime.now(IST)
    with pytest.raises(HttpError):
        p.upload(p.test_id)
    retry = p.posts.conn.execute('SELECT retry_after FROM upload_retries WHERE opportunity_id=?', (p.test_id,)).fetchone()
    delay = (datetime.fromisoformat(retry[0]) - before).total_seconds()
    assert 3590 <= delay <= 3610
    assert p.posts.get(p.test_id).status == 'ready'


def test_online_backup_is_restorable_and_closed(pipeline):
    import sqlite3
    from shorts.production import backup_database
    target = backup_database(pipeline.collector_settings['db_path'])
    connection = sqlite3.connect(target)
    try:
        assert connection.execute('SELECT COUNT(*) FROM opportunities').fetchone()[0] == 1
        assert connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    finally:
        connection.close()
    assert backup_database(pipeline.collector_settings['db_path']) == target


def test_public_metrics_readback(pipeline):
    from shorts.production import sync_statistics
    p = pipeline
    p.posts.upsert(__import__('shorts.models', fromlist=['PostRecord']).PostRecord(p.test_id, '{}', youtube_id='abcdefghijk', status='posted'))
    service = Mock()
    service.videos().list().execute.return_value = {'items': [{'id': 'abcdefghijk',
        'statistics': {'viewCount': '42', 'likeCount': '3'}, 'status': {'privacyStatus': 'public', 'uploadStatus': 'processed'}}]}
    report = sync_statistics(p, service)
    assert report['videos'][0]['views'] == 42
    assert report['videos'][0]['likes'] == 3
    assert 'Retention' in report['limits']


def test_expired_closed_and_scam_rejected(pipeline):
    p = pipeline
    for assignment in ("deadline='2000-01-01'", "deadline=NULL, is_open=0", "is_open=1, description='registration fee required'"):
        p.db.conn.execute(f'UPDATE opportunities SET {assignment} WHERE id=?', (p.test_id,))
        p.db.conn.commit()
        with pytest.raises(ValueError):
            p.build(p.test_id)


def test_automatic_upload_requires_recent_source_check(pipeline, monkeypatch):
    p = pipeline
    p.settings['automation']['enabled'] = True
    mock_media(monkeypatch)
    p.build(p.test_id)
    p.db.conn.execute("UPDATE opportunities SET last_seen_at='2000-01-01T00:00:00Z' WHERE id=?", (p.test_id,))
    p.db.conn.commit()
    upload = Mock()
    monkeypatch.setattr('shorts.upload.upload_video', upload)
    with pytest.raises(ValueError, match='stale'):
        p.upload(p.test_id)
    upload.assert_not_called()


def test_edited_script_requires_reapproval(pipeline, monkeypatch):
    p = pipeline
    mock_media(monkeypatch)
    p.build(p.test_id)
    p.db.set_status(p.test_id, 'approved')
    p.approve_video(p.test_id)
    script = _template_fallback(p.card(p.test_id), p.settings)
    p.script(p.test_id, script)
    assert p.posts.get(p.test_id).status == 'pending'
    with pytest.raises(ValueError):
        p.upload(p.test_id)


def test_fact_validation(pipeline):
    p = pipeline
    card = p.card(p.test_id)
    script = _template_fallback(card, p.settings)
    assert validate_script(script, card)[0]
    script.voiceover_lines[1].text += ' Salary Rs 99,999.'
    assert not validate_script(script, card)[0]
    script = _template_fallback(card, p.settings)
    script.description += '\nhttps://evil.example/redirect'
    assert not validate_script(script, card)[0]
    script = _template_fallback(card, p.settings)
    script.on_screen.location = 'London'
    assert not validate_script(script, card)[0]


def test_schedule_and_runner(pipeline, monkeypatch):
    p = pipeline
    mock_media(monkeypatch)
    p.build(p.test_id)
    p.db.set_status(p.test_id, 'approved')
    p.approve_video(p.test_id)
    schedule(p, p.test_id, (datetime.now(IST)+timedelta(days=1)).isoformat())
    p.posts.conn.execute('UPDATE schedules SET scheduled_at=?', ((datetime.now(IST)-timedelta(minutes=1)).isoformat(),))
    p.posts.conn.commit()
    result = run_daily(p.config_dir, collect=False, manual_export=True)
    assert not result['errors']
    assert len(result['uploaded']) == 1
    assert p.posts.conn.execute('SELECT COUNT(*) FROM schedules').fetchone()[0] == 0


def test_changed_listing_requires_new_preview(pipeline, monkeypatch):
    p = pipeline
    mock_media(monkeypatch)
    p.build(p.test_id)
    p.db.set_status(p.test_id, 'approved')
    p.approve_video(p.test_id)
    p.db.conn.execute('UPDATE opportunities SET location=? WHERE id=?', ('Mumbai, India', p.test_id))
    p.db.conn.commit()
    with pytest.raises(ValueError, match='changed'):
        p.upload(p.test_id, manual_export=True)


def test_daily_limit_counts_failed_attempts(pipeline, monkeypatch):
    p = pipeline
    mock_media(monkeypatch)
    p.build(p.test_id)
    p.db.set_status(p.test_id, 'approved')
    p.approve_video(p.test_id)
    p.settings['upload']['daily_limit'] = 1
    p.posts.conn.execute('INSERT INTO upload_attempts VALUES (?, ?, ?, ?)',
        ('another', 'different', 'role', datetime.now(IST).astimezone(__import__('datetime').timezone.utc).isoformat()))
    p.posts.conn.commit()
    upload = Mock()
    monkeypatch.setattr('shorts.upload.upload_video', upload)
    with pytest.raises(ValueError, match='limit'):
        p.upload(p.test_id)
    upload.assert_not_called()


def test_automatic_build_and_upload_without_approvals(pipeline, monkeypatch):
    p = pipeline
    p.settings['automation']['enabled'] = True
    mock_media(monkeypatch)
    assert p.db.get(p.test_id)['status'] == 'new'
    assert p.build(p.test_id).status == 'ready'
    upload = Mock(return_value='abcdefghijk')
    monkeypatch.setattr('shorts.upload.upload_video', upload)
    assert p.upload(p.test_id) == 'abcdefghijk'
    assert p.db.get(p.test_id)['status'] == 'posted'
    assert p.upload(p.test_id) == 'abcdefghijk'
    assert upload.call_count == 1


def test_automatic_runner_schedules_once_and_ignores_rejected(pipeline, monkeypatch):
    from shorts.scheduler import run_automatic
    p = pipeline
    p.settings['automation']['enabled'] = True
    mock_media(monkeypatch)
    empty = lambda: {'generated': [], 'uploaded': [], 'errors': []}
    result = run_automatic(p, empty())
    assert result['generated'] == [p.test_id]
    assert not result['errors']
    assert not run_automatic(p, empty())['generated']
    assert p.posts.conn.execute('SELECT COUNT(*) FROM schedules').fetchone()[0] == 1
    p.db.set_status(p.test_id, 'rejected')
    with pytest.raises(ValueError, match='rejected'):
        p.upload(p.test_id)


def test_automatic_changed_facts_regenerate(pipeline, monkeypatch):
    p = pipeline
    p.settings['automation']['enabled'] = True
    tts = mock_media(monkeypatch)
    p.build(p.test_id)
    p.db.conn.execute('UPDATE opportunities SET location=? WHERE id=?', ('Mumbai, India', p.test_id))
    p.db.conn.commit()
    p.build(p.test_id)
    assert tts.call_count == 2
    assert 'Mumbai' in p.posts.get(p.test_id).script_json


def test_immediate_publishes_new_video_in_same_cycle(pipeline, monkeypatch):
    from shorts.scheduler import run_automatic
    p = pipeline
    p.settings['automation'].update(enabled=True, publishing_mode='immediate')
    mock_media(monkeypatch)
    monkeypatch.setattr('shorts.upload.youtube_service', Mock())
    monkeypatch.setattr('shorts.upload.reconcile_pending', lambda *args: [])
    upload = Mock(return_value='abcdefghijk')
    monkeypatch.setattr('shorts.upload.upload_video', upload)
    result = run_automatic(p, {'generated': [], 'uploaded': [], 'errors': []}, upload=True)
    assert result['generated'] == [p.test_id]
    assert result['uploaded'] == ['abcdefghijk']
    assert not result['errors']
    assert p.posts.conn.execute('SELECT COUNT(*) FROM schedules').fetchone()[0] == 0
    upload.assert_called_once()


def test_immediate_drains_future_queue_and_keeps_idempotency(pipeline, monkeypatch):
    from shorts.scheduler import run_automatic
    p = pipeline
    p.settings['automation'].update(enabled=True, publishing_mode='immediate')
    mock_media(monkeypatch)
    p.build(p.test_id)
    schedule(p, p.test_id, (datetime.now(IST) + timedelta(days=1)).isoformat())
    monkeypatch.setattr('shorts.upload.youtube_service', Mock())
    monkeypatch.setattr('shorts.upload.reconcile_pending', lambda *args: [])
    upload = Mock(return_value='abcdefghijk')
    monkeypatch.setattr('shorts.upload.upload_video', upload)
    empty = lambda: {'generated': [], 'uploaded': [], 'errors': []}
    assert run_automatic(p, empty(), upload=True)['uploaded'] == ['abcdefghijk']
    assert not run_automatic(p, empty(), upload=True)['uploaded']
    upload.assert_called_once()


def test_new_high_paid_candidate_precedes_existing_ready_queue(pipeline, monkeypatch):
    from shorts.scheduler import run_automatic
    p = pipeline
    p.settings['automation'].update(enabled=True, publishing_mode='immediate', max_builds_per_run=1)
    mock_media(monkeypatch)
    p.build(p.test_id)
    schedule(p, p.test_id, (datetime.now(IST) + timedelta(days=1)).isoformat())
    high = Opportunity(source='manual', board='manual', external_id='high',
        title='Data Engineering Intern', company='Higher Paid Corp',
        location='India', apply_url='https://example.com/high',
        description='Students can apply through the official careers page.',
        stipend_text='INR 55000/month', opp_type='internship')
    p.db.upsert(high)
    result = run_automatic(p, {'generated': [], 'uploaded': [], 'errors': []})
    assert result['generated'] == [high.id]
    assert not result['errors']


def test_channel_backoff_prevents_wasted_generation(pipeline, monkeypatch):
    from shorts.scheduler import run_automatic
    p = pipeline
    p.settings['automation'].update(enabled=True, publishing_mode='immediate')
    until = (datetime.now(IST) + timedelta(hours=1)).isoformat()
    p.posts.conn.execute('INSERT INTO youtube_backoff VALUES (?,?,?)',
        (p.settings['upload'].get('expected_channel_id', ''), until, 'limit'))
    p.posts.conn.commit()
    build = Mock()
    monkeypatch.setattr(p, 'build', build)
    result = run_automatic(p, {'generated': [], 'uploaded': [], 'errors': []})
    assert result['paused_until'] == until
    build.assert_not_called()


def test_stale_candidate_does_not_consume_generation(pipeline, monkeypatch):
    from shorts.scheduler import run_automatic
    p = pipeline
    p.settings['automation'].update(enabled=True, publishing_mode='immediate')
    p.db.conn.execute("UPDATE opportunities SET last_seen_at='2000-01-01T00:00:00Z'")
    p.db.conn.commit()
    build = Mock()
    monkeypatch.setattr(p, 'build', build)
    run_automatic(p, {'generated': [], 'uploaded': [], 'errors': []})
    build.assert_not_called()


def test_youtube_spacing_survives_new_cycle(pipeline, monkeypatch):
    from shorts.scheduler import run_automatic
    p = pipeline
    p.settings['automation'].update(enabled=True, publishing_mode='immediate', min_upload_interval_minutes=144)
    p.posts.conn.execute("INSERT INTO posts(opportunity_id,script_json,status,posted_at) VALUES ('previous','{}','posted',?)", (datetime.now(IST).isoformat(),))
    p.posts.conn.commit()
    build = Mock()
    monkeypatch.setattr(p, 'build', build)
    result = run_automatic(p, {'generated': [], 'uploaded': [], 'errors': []})
    assert 'next_upload_at' in result
    build.assert_not_called()


def test_immediate_stops_generation_at_daily_quota(pipeline, monkeypatch):
    from shorts.scheduler import run_automatic
    from datetime import timezone
    p = pipeline
    p.settings['automation'].update(enabled=True, publishing_mode='immediate')
    p.settings['upload']['daily_limit'] = 1
    p.posts.conn.execute('INSERT INTO upload_attempts VALUES (?, ?, ?, ?)',
        ('other', 'other', 'role', datetime.now(IST).astimezone(timezone.utc).isoformat()))
    p.posts.conn.commit()
    build = Mock()
    monkeypatch.setattr(p, 'build', build)
    result = run_automatic(p, {'generated': [], 'uploaded': [], 'errors': []})
    assert not result['generated']
    build.assert_not_called()


def test_automatic_failed_item_is_deferred(pipeline, monkeypatch):
    from shorts.scheduler import run_automatic
    p = pipeline
    p.settings['automation']['enabled'] = True
    build = Mock(side_effect=RuntimeError('temporary failure'))
    monkeypatch.setattr(p, 'build', build)
    empty = lambda: {'generated': [], 'uploaded': [], 'errors': []}
    assert run_automatic(p, empty())['errors']
    assert p.posts.get(p.test_id).status == 'failed'
    assert not run_automatic(p, empty())['errors']
    assert build.call_count == 1


def test_automatic_model_change_invalidates_cache(pipeline, monkeypatch):
    p = pipeline
    p.settings['automation']['enabled'] = True
    tts = mock_media(monkeypatch)
    p.build(p.test_id)
    p.settings['llm']['model'] = 'a-different-local-model'
    p.build(p.test_id)
    # Identity changes must not silently retain an old producer's script/video.
    manifest = json.loads((Path(p.settings['paths']['output_dir']) / p.test_id / 'manifest.json').read_text())
    assert manifest['llm']['model'] == 'a-different-local-model'
    assert tts.call_count == 2


def test_lost_upload_response_reconciles_automatically(pipeline, monkeypatch):
    from shorts.upload import reconcile_pending
    p = pipeline
    mock_media(monkeypatch)
    p.build(p.test_id)
    p.posts.update_status(p.test_id, 'uploading')
    script = json.loads(p.posts.get(p.test_id).script_json)
    service = Mock()
    service.channels().list().execute.return_value = {'items': [
        {'contentDetails': {'relatedPlaylists': {'uploads': 'playlist'}}}]}
    service.playlistItems().list().execute.return_value = {'items': [
        {'contentDetails': {'videoId': 'abcdefghijk'}}]}
    service.videos().list().execute.return_value = {'items': [
        {'id': 'abcdefghijk', 'snippet': {'title': script['title'], 'description': script['description']}}]}
    assert reconcile_pending(p, service) == ['abcdefghijk']
    assert p.posts.get(p.test_id).status == 'posted'
    assert p.db.get(p.test_id)['status'] == 'posted'
    service.videos().insert.assert_not_called()


def test_ambiguous_upload_recovery_does_not_duplicate(pipeline, monkeypatch):
    from shorts.upload import reconcile_pending
    p = pipeline
    mock_media(monkeypatch)
    p.build(p.test_id)
    p.posts.update_status(p.test_id, 'uploading')
    script = json.loads(p.posts.get(p.test_id).script_json)
    service = Mock()
    service.channels().list().execute.return_value = {'items': [
        {'contentDetails': {'relatedPlaylists': {'uploads': 'playlist'}}}]}
    service.playlistItems().list().execute.return_value = {'items': [
        {'contentDetails': {'videoId': 'abcdefghijk'}}, {'contentDetails': {'videoId': 'lmnopqrstuv'}}]}
    snippet = {'title': script['title'], 'description': script['description']}
    service.videos().list().execute.return_value = {'items': [
        {'id': 'abcdefghijk', 'snippet': snippet}, {'id': 'lmnopqrstuv', 'snippet': snippet}]}
    assert reconcile_pending(p, service) == []
    assert p.posts.get(p.test_id).status == 'uploading'
    service.videos().insert.assert_not_called()


def test_dashboard_review(pipeline, monkeypatch):
    monkeypatch.setenv('SHORTS_CONFIG_DIR', str(pipeline.config_dir))
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file(str(Path(__file__).parents[1] / 'shorts' / 'review_app' / 'app.py'), default_timeout=10).run()
    assert not app.exception
    button = next(button for button in app.button if button.label == 'Approve opportunity')
    button.click().run()
    assert not app.exception
    assert pipeline.db.get(pipeline.test_id)['status'] == 'approved'


def test_expired_youtube_connection_stops_generation(pipeline, monkeypatch):
    from shorts.scheduler import run_automatic
    p = pipeline
    p.settings['automation'].update(enabled=True, publishing_mode='immediate')
    monkeypatch.setattr('shorts.upload.youtube_service', Mock(side_effect=ValueError('YouTube authorization expired')))
    build = Mock()
    monkeypatch.setattr(p, 'build', build)
    result = run_automatic(p, {'generated': [], 'uploaded': [], 'errors': []}, upload=True)
    assert result['youtube_connection_blocked'] is True
    build.assert_not_called()
