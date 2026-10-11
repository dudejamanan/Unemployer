from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

SCOPES = ['https://www.googleapis.com/auth/youtube.upload']


def export_manual(post, script, settings):
    from .pipeline import IST
    from .trust import promoted_script
    folder = Path(settings['paths']['output_dir']) / 'exports' / datetime.now(IST).date().isoformat() / post.opportunity_id
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copy2(post.video_path, folder / 'video.mp4')
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
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    token = Path(settings['youtube_token_file'])
    credentials = Credentials.from_authorized_user_file(str(token), SCOPES) if token.exists() else None
    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
    if not credentials or not credentials.valid:
        if not interactive:
            raise ValueError('Run python -m shorts auth to authorize YouTube first')
        secrets = settings.get('youtube_client_secrets_file')
        if not secrets or not Path(secrets).is_file():
            raise ValueError('Set YOUTUBE_CLIENT_SECRETS_FILE to a Desktop OAuth client JSON')
        credentials = InstalledAppFlow.from_client_secrets_file(secrets, SCOPES).run_local_server(port=0)
    token.parent.mkdir(parents=True, exist_ok=True)
    token.write_text(credentials.to_json(), encoding='utf-8')
    return build('youtube', 'v3', credentials=credentials, cache_discovery=False)


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
    return response['id']
