from unittest.mock import Mock
import pytest
from shorts.upload import upload_video
from shorts.models import PostRecord
from shorts.settings import load_shorts_settings
from shorts.script_gen import _template_fallback
from shorts.validate_script import validate_script


def card():
    return {'id': 'example', 'company': 'Example', 'role': 'Engineering Intern',
            'location': 'India', 'stipend': '', 'batch_years': [], 'experience': '',
            'deadline': None, 'description': '', 'apply_url': 'https://example.com/apply', 'type': 'internship'}


def test_resumable_upload_metadata(tmp_path):
    settings = load_shorts_settings()
    script = _template_fallback(card(), settings)
    video = tmp_path / 'video.mp4'
    video.write_bytes(b'fixture')
    post = PostRecord('example', '{}', video_path=str(video))
    service = Mock()
    service.videos().insert().next_chunk.side_effect = [(None, None), (None, {'id': 'abcdefghijk'})]
    assert upload_video(post, script, settings, service) == 'abcdefghijk'
    args = service.videos().insert.call_args.kwargs
    assert args['body']['status']['privacyStatus'] == settings['upload'].get('privacy', 'private')
    assert args['body']['status']['containsSyntheticMedia'] is True
    assert args['body']['status']['selfDeclaredMadeForKids'] is False
    assert args['body']['snippet']['categoryId'] == '27'
    assert args['media_body'].resumable()


def test_missing_video_id_is_error(tmp_path):
    video = tmp_path / 'video.mp4'
    video.write_bytes(b'fixture')
    settings = load_shorts_settings()
    script = _template_fallback(card(), settings)
    service = Mock()
    service.videos().insert().next_chunk.return_value = (None, {})
    with pytest.raises(RuntimeError, match='no video ID'):
        upload_video(PostRecord('example', '{}', video_path=str(video)), script, settings, service)


def test_promoted_listing_requires_disclosure(tmp_path):
    data = card()
    data['description'] = 'Promoted: A paid listing from the company.'
    settings = load_shorts_settings()
    script = _template_fallback(data, settings)
    assert validate_script(script, data)[0]
    video = tmp_path / 'video.mp4'
    video.write_bytes(b'fixture')
    service = Mock()
    service.videos().insert().next_chunk.return_value = (None, {'id': 'abcdefghijk'})
    upload_video(PostRecord('example', '{}', video_path=str(video)), script, settings, service)
    args = service.videos().insert.call_args.kwargs
    assert args['body']['paidProductPlacementDetails']['hasPaidProductPlacement']
    script.description = script.description.replace('Promoted listing', '')
    assert not validate_script(script, data)[0]
