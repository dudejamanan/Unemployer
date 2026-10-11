"""Audit public video-description links; never downloads or republishes videos."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import argparse
import json
import re
import requests

ROOT = Path(__file__).resolve().parents[1]


def initial_json(html, name):
    match = re.search(r'(?:var\s+)?' + re.escape(name) + r'\s*=\s*', html)
    if match:
        try:
            return json.JSONDecoder().raw_decode(html[match.end():])[0]
        except ValueError:
            pass
    return {}


def videos_in(value):
    if isinstance(value, dict):
        renderer = value.get('videoRenderer') or value.get('gridVideoRenderer')
        if renderer and renderer.get('videoId'):
            yield renderer
        lockup = value.get('lockupViewModel')
        if lockup and lockup.get('contentType') == 'LOCKUP_CONTENT_TYPE_VIDEO':
            title = lockup.get('metadata', {}).get('lockupMetadataViewModel', {}).get('title', {}).get('content', '')
            yield {'videoId': lockup['contentId'], 'title': {'runs': [{'text': title}]}}
        for child in value.values():
            yield from videos_in(child)
    elif isinstance(value, list):
        for child in value:
            yield from videos_in(child)


def get(url):
    response = requests.get(url, timeout=25, headers={'User-Agent': 'OpportunityShortsBot/0.1'})
    response.raise_for_status()
    return response.text


def inspect_video(video):
    video_id = video['videoId']
    url = 'https://www.youtube.com/watch?v=' + video_id
    title = ''.join(run.get('text', '') for run in video.get('title', {}).get('runs', []))
    try:
        html = get(url)
        player = initial_json(html, 'ytInitialPlayerResponse')
        description = player.get('videoDetails', {}).get('shortDescription', '')
        links = []
        for link in re.findall(r'https?://[^\s<>]+', description):
            link = link.rstrip('.,)')
            parsed = urlparse(link)
            if parsed.netloc.endswith('youtube.com') and parsed.path == '/redirect':
                link = parse_qs(parsed.query).get('q', [link])[0]
            links.append(link)
        details = player.get('videoDetails', {})
        return {'title': details.get('title', title), 'video': url,
                'description_available': bool(description), 'description': description,
                'views': details.get('viewCount'), 'duration_seconds': details.get('lengthSeconds'),
                'hashtags': list(dict.fromkeys(re.findall(r'#[\w]+', description))),
                'links': list(dict.fromkeys(links))}
    except requests.RequestException as exc:
        return {'title': title, 'video': url, 'error': type(exc).__name__}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--channel', default='https://www.youtube.com/@ashishcode')
    parser.add_argument('--limit', type=int, default=10)
    parser.add_argument('--output', default='channel_sources.json')
    parser.add_argument('--quiet', action='store_true')
    args = parser.parse_args()
    html = get(args.channel.rstrip('/') + '/videos')
    folder = ROOT / 'data' / 'source_probes'
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'channel.html').write_text(html, encoding='utf-8')
    data = initial_json(html, 'ytInitialData')
    videos = list({v['videoId']: v for v in videos_in(data)}.values())[:min(args.limit, 30)]
    if not videos:
        raise SystemExit('No public video metadata extracted; the channel page format may have changed.')
    report = {'channel': args.channel, 'videos': []}
    with ThreadPoolExecutor(max_workers=3) as executor:
        for item in executor.map(inspect_video, videos):
            report['videos'].append(item)
            if not args.quiet:
                print(json.dumps(item), flush=True)
    path = ROOT / 'data' / 'source_probes' / Path(args.output).name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('Videos audited:', len(report['videos']))


if __name__ == '__main__':
    main()
