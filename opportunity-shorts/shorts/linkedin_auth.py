"""Local OAuth callback with state validation; secrets never printed."""
import json
import os
import secrets
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlencode, urlsplit, parse_qs
from pathlib import Path
import requests
from .production import atomic_json


def authorize(cfg):
    from collector.config import ROOT
    author = cfg.get('author', '')
    import re
    if not re.fullmatch(r'urn:li:organization:\d+', author):
        raise ValueError('Set LINKEDIN_ORGANIZATION_URN first')
    client = os.getenv('LINKEDIN_CLIENT_ID')
    secret = os.getenv('LINKEDIN_CLIENT_SECRET')
    if not client or not secret:
        raise ValueError('Set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET in your private .env')
    redirect = 'http://localhost:8766/callback'
    state = secrets.token_urlsafe(32)
    result = {}
    class Callback(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_GET(self):
            parsed = urlsplit(self.path)
            query = parse_qs(parsed.query)
            valid = parsed.path == '/callback' and secrets.compare_digest(query.get('state', [''])[0], state)
            self.send_response(200 if valid else 400)
            self.end_headers()
            if valid:
                result.update(code=query.get('code', [''])[0], error=query.get('error', [''])[0])
                self.wfile.write(b'Authorization received. Return to the terminal.')
            else:
                self.wfile.write(b'Invalid authorization callback.')
    server = HTTPServer(('127.0.0.1', 8766), Callback)
    server.timeout = 1
    url = 'https://www.linkedin.com/oauth/v2/authorization?' + urlencode(dict(response_type='code', client_id=client, redirect_uri=redirect, state=state, scope='w_organization_social r_organization_social'))
    print('Opening LinkedIn admin authorization; callback timeout is five minutes.')
    webbrowser.open(url)
    deadline = time.monotonic() + 300
    try:
        while not result and time.monotonic() < deadline:
            server.handle_request()
    finally:
        server.server_close()
    if not result.get('code') or result.get('error'):
        raise ValueError('LinkedIn authorization denied or timed out')
    response = requests.post('https://www.linkedin.com/oauth/v2/accessToken', data=dict(grant_type='authorization_code', code=result['code'], redirect_uri=redirect, client_id=client, client_secret=secret), timeout=(10, 30))
    if response.status_code != 200:
        raise ValueError('LinkedIn token exchange rejected; check developer app credentials and access')
    token = response.json()
    if not token.get('access_token') or not token.get('expires_in'):
        raise ValueError('LinkedIn returned an incomplete token')
    token['expires_at'] = time.time() + int(token['expires_in'])
    token['author'] = author
    path = Path(os.getenv('LINKEDIN_TOKEN_FILE', 'secrets/linkedin_token.json'))
    if not path.is_absolute():
        path = ROOT / path
    atomic_json(path, token)
    print('LinkedIn token saved privately. Verify the page authorization before enabling publishing.')
