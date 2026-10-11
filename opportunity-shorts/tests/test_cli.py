from collector.cli import parse_board_url


def test_parse_board_urls():
    assert parse_board_url("https://boards.greenhouse.io/stripe/jobs/123") == {"ats": "greenhouse", "token": "stripe"}
    assert parse_board_url("https://job-boards.greenhouse.io/anthropic") == {"ats": "greenhouse", "token": "anthropic"}
    assert parse_board_url("https://jobs.lever.co/spotify/abc") == {"ats": "lever", "token": "spotify"}
    assert parse_board_url("https://jobs.eu.lever.co/acme") == {"ats": "lever", "token": "acme", "region": "eu"}
    assert parse_board_url("https://jobs.ashbyhq.com/notion") == {"ats": "ashby", "token": "notion"}
    assert parse_board_url("https://example.com/careers") is None
