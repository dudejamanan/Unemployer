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
    (config / 'shorts.yaml').write_text(f'paths:\n  output_dir: {tmp_path.as_posix()}/out\n')
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


def test_expired_closed_and_scam_rejected(pipeline):
    p = pipeline
    for assignment in ("deadline='2000-01-01'", "deadline=NULL, is_open=0", "is_open=1, description='registration fee required'"):
        p.db.conn.execute(f'UPDATE opportunities SET {assignment} WHERE id=?', (p.test_id,))
        p.db.conn.commit()
        with pytest.raises(ValueError):
            p.build(p.test_id)


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


def test_dashboard_review(pipeline):
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file(str(Path(__file__).parents[1] / 'shorts' / 'review_app' / 'app.py'), default_timeout=10).run()
    assert not app.exception
    button = next(button for button in app.button if button.label == 'Approve opportunity')
    button.click().run()
    assert not app.exception
    assert pipeline.db.get(pipeline.test_id)['status'] == 'approved'
