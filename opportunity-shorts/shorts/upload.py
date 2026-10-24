from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

SCOPES = ['https://www.googleapis.com/auth/youtube.upload',
          'https://www.googleapis.com/auth/youtube.readonly']


def export_manual(post, script, settings):
    from .pipeline import IST
    from .trust import promoted_script
    folder = Path(settings['paths']['output_dir']) / 'exports' / datetime.now(IST).date().isoformat() / post.opportunity_id
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copy2(post.video_path, folder / 'video.mp4')
    thumbnail = Path(post.video_path).parent / 'thumbnail.png'
    if thumbnail.is_file():
        shutil.copy2(thumbnail, folder / 'thumbnail.png')
    (folder / 'title.txt').write_text(script.title, encoding='utf-8')
    (folder / 'description.txt').write_text(script.description, encoding='utf-8')
    (folder / 'upload_settings.json').write_text(json.dumps({
        'made_for_kids': settings['upload']['made_for_kids'],
        'contains_synthetic_media': settings['upload'].get('contains_synthetic_media', True),
        'privacy': settings['upload'].get('privacy', 'private'),
        'paid_promotion': promoted_script(script),
    }, indent=2), encoding='utf-8')
    return folder


def youtube_service(settings, interactive=False):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google.auth.exceptions import RefreshError
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from google_auth_httplib2 import AuthorizedHttp
    import httplib2
    token = Path(settings['youtube_token_file'])
    credentials = Credentials.from_authorized_user_file(str(token)) if token.exists() else None
    if credentials and not credentials.has_scopes(SCOPES):
        credentials = None
    if credentials and credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
        except RefreshError:
            if not interactive:
                raise ValueError('YouTube authorization expired or revoked; run python -m shorts auth to reconnect') from None
            credentials = None
    if not credentials or not credentials.valid:
        if not interactive:
            raise ValueError('Run python -m shorts auth to authorize YouTube first')
        secrets = settings.get('youtube_client_secrets_file')
        if not secrets or not Path(secrets).is_file():
            raise ValueError('Set YOUTUBE_CLIENT_SECRETS_FILE to a Desktop OAuth client JSON')
        credentials = InstalledAppFlow.from_client_secrets_file(secrets, SCOPES).run_local_server(
            port=0, timeout_seconds=300, prompt='consent', authorization_prompt_message='')
    token.parent.mkdir(parents=True, exist_ok=True)
    token.write_text(credentials.to_json(), encoding='utf-8')
    service = build('youtube', 'v3', http=AuthorizedHttp(credentials, http=httplib2.Http(timeout=30)), cache_discovery=False)
    expected = settings['upload'].get('expected_channel_handle')
    expected_id = settings['upload'].get('expected_channel_id')
    if expected or expected_id:
        channels = service.channels().list(part='id,snippet', mine=True).execute().get('items', [])
        matches = [channel for channel in channels if
                   (channel['id'] == expected_id if expected_id else
                    channel['snippet'].get('customUrl', '').lstrip('@').casefold() == expected.lstrip('@').casefold())]
        if len(matches) != 1:
            raise ValueError('Authorized account is not the configured channel; run auth and select @unemployerr')
    return service


def upload_video(post, script, settings, service=None):
    from googleapiclient.http import MediaFileUpload
    from .trust import promoted_script
    service = service or youtube_service(settings)
    cfg = settings['upload']
    privacy = cfg.get('privacy', 'private')
    if privacy not in ('private', 'unlisted', 'public'):
        raise ValueError('Invalid upload privacy')
    body = {
        'snippet': {'title': script.title, 'description': script.description,
                    'tags': list(dict.fromkeys(t.lstrip('#') for t in script.hashtags)),
                    'categoryId': str(cfg['category_id']), 'defaultLanguage': 'en'},
        'status': {'privacyStatus': privacy, 'selfDeclaredMadeForKids': cfg['made_for_kids'],
                   'containsSyntheticMedia': cfg.get('contains_synthetic_media', True)},
    }
    part = 'snippet,status'
    if promoted_script(script):
        body['paidProductPlacementDetails'] = {'hasPaidProductPlacement': True}
        part += ',paidProductPlacementDetails'
    request = service.videos().insert(part=part, body=body,
        media_body=MediaFileUpload(post.video_path, mimetype='video/mp4', resumable=True))
    response = None
    while response is None:
        _, response = request.next_chunk(num_retries=3)
    if not response.get('id'):
        raise RuntimeError('Upload response contains no video ID; reconcile in YouTube Studio')
    thumbnail = Path(post.video_path).parent / 'thumbnail.png'
    if settings['upload'].get('set_thumbnail', False) and thumbnail.is_file():
        # Thumbnail eligibility/errors must never turn a successful video into a retry.
        set_cover_thumbnail(response['id'], thumbnail, settings, service)
    return response['id']


def set_cover_thumbnail(video_id, image_path, settings, service=None):
    """Best-effort custom cover; Shorts/channel eligibility is decided by YouTube."""
    from googleapiclient.http import MediaFileUpload
    result = {'video_id': video_id, 'status': 'unavailable'}
    try:
        service = service or youtube_service(settings)
        response = service.thumbnails().set(videoId=video_id,
            media_body=MediaFileUpload(str(image_path), mimetype='image/png', resumable=False)).execute()
        if isinstance(response, dict) and response.get('items'):
            result['status'] = 'set'
        else:
            result['message'] = 'YouTube did not confirm a custom thumbnail; select the opening frame in the app'
    except Exception as exc:
        result['message'] = 'Custom thumbnail unavailable; video upload preserved. Select the opening frame in YouTube.'
        result['error_type'] = type(exc).__name__
    try:
        from .production import atomic_json
        atomic_json(Path(image_path).parent / 'thumbnail-upload.json', result)
    except OSError:
        pass
    return result


def reconcile_pending(pipeline, service):
    """Find an accepted upload after a lost response; never blindly insert again."""
    pending = pipeline.posts.conn.execute("SELECT * FROM posts WHERE status='uploading'").fetchall()
    if not pending:
        return []
    channels = service.channels().list(part='contentDetails', mine=True).execute().get('items', [])
    video_ids = []
    for channel in channels:
        playlist = channel['contentDetails']['relatedPlaylists']['uploads']
        items = service.playlistItems().list(part='contentDetails', playlistId=playlist, maxResults=50).execute().get('items', [])
        video_ids.extend(item['contentDetails']['videoId'] for item in items)
    if not video_ids:
        return []
    videos = []
    for offset in range(0, len(video_ids), 50):
        videos.extend(service.videos().list(part='snippet', id=','.join(video_ids[offset:offset+50])).execute().get('items', []))
    found = []
    for post in pending:
        script = json.loads(post['script_json'])
        matches = [video for video in videos if video['snippet'].get('title') == script['title']
                   and video['snippet'].get('description') == script['description']]
        if len(matches) == 1:
            pipeline.posts.set_youtube_id(post['opportunity_id'], matches[0]['id'])
            pipeline.db.set_status(post['opportunity_id'], 'posted')
            pipeline.posts.conn.execute('DELETE FROM schedules WHERE opportunity_id=?', (post['opportunity_id'],))
            pipeline.posts.conn.commit()
            found.append(matches[0]['id'])
    return found
