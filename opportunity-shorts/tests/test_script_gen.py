from __future__ import annotations

import pytest

from shorts.script_gen import generate_script, _template_fallback, count_words
from shorts.validate_script import validate_script
from shorts.settings import load_shorts_settings

# Sample cards for golden tests
CARD_INTERNSHIP_WITH_STIPEND = {
    "id": "test1",
    "type": "internship",
    "role": "Software Engineering Intern",
    "company": "Google",
    "location": "Bengaluru, India",
    "is_india": True,
    "is_remote": False,
    "stipend": "Rs 80,000 per month",
    "batch_years": [2027, 2028],
    "experience": "Freshers welcome",
    "deadline": "2026-11-15",
    "apply_url": "https://careers.google.com/jobs/123",
    "description": "Join our team as an intern.",
    "posted_at": "2026-10-05T09:00:00Z",
    "score": 90.0,
    "verified": True,
    "source": "manual",
    "status": "approved",
}

CARD_JOB_NO_DEADLINE = {
    "id": "test2",
    "type": "job",
    "role": "Associate Software Engineer",
    "company": "Flipkart",
    "location": "Bengaluru, India",
    "is_india": True,
    "is_remote": False,
    "stipend": "",
    "batch_years": [],
    "experience": "0-2 years",
    "deadline": None,
    "apply_url": "https://jobs.flipkart.com/careers/456",
    "description": "Full-time role for freshers.",
    "posted_at": "2026-10-05T09:00:00Z",
    "score": 85.0,
    "verified": True,
    "source": "manual",
    "status": "approved",
}

CARD_HACKATHON = {
    "id": "test3",
    "type": "hackathon",
    "role": "Smart India Hackathon 2026",
    "company": "Government of India",
    "location": "Pan India",
    "is_india": True,
    "is_remote": False,
    "stipend": "Prize pool ₹10 lakh",
    "batch_years": [2026, 2027, 2028],
    "experience": "",
    "deadline": "2026-10-20",
    "apply_url": "https://www.sih.gov.in/register",
    "description": "National level hackathon for students.",
    "posted_at": "2026-10-05T09:00:00Z",
    "score": 95.0,
    "verified": True,
    "source": "manual",
    "status": "approved",
}


def test_date_detection_does_not_treat_url_ids_or_company_prefixes_as_months():
    from shorts.validate_script import extract_dates
    assert extract_dates('https://example.com/1280\nMarketing Intern at Juniper Networks') == []
    assert extract_dates('Apply by 15 Nov 2026. Another date is March 2, 2027.') == ['15 Nov 2026', 'March 2, 2027']
    card = dict(CARD_JOB_NO_DEADLINE, role='Marketing Intern', company='Juniper Networks',
                apply_url='https://example.com/job/1280')
    assert validate_script(_template_fallback(card, load_shorts_settings()), card)[0]


def test_wrong_year_is_not_hidden_by_matching_day_and_month():
    card = dict(CARD_INTERNSHIP_WITH_STIPEND, batch_years=[2026, 2027])
    script = _template_fallback(card, load_shorts_settings())
    script.hook = 'Apply by 15 Nov 2027.'
    assert any('Unsupported date: 15 Nov 2027' in error for error in validate_script(script, card)[1])


def test_template_fallback_internship():
    """Test template fallback for internship with stipend."""
    settings = load_shorts_settings()
    script = _template_fallback(CARD_INTERNSHIP_WITH_STIPEND, settings)

    assert script.hook
    assert "Google" in script.hook
    assert "Software Engineering Intern" in script.hook
    assert len(script.voiceover_lines) > 0
    assert script.on_screen.company == "Google"
    assert script.on_screen.role == "Software Engineering Intern"
    assert script.on_screen.stipend == "Rs 80,000 per month"
    assert "2027" in script.on_screen.eligibility or "2028" in script.on_screen.eligibility
    assert len(script.title) <= 100
    assert CARD_INTERNSHIP_WITH_STIPEND["apply_url"] in script.description
    assert "official site" in script.description.lower()
    assert "#Shorts" in script.description


def test_template_fallback_job_no_deadline():
    """Test template fallback for job without deadline."""
    settings = load_shorts_settings()
    script = _template_fallback(CARD_JOB_NO_DEADLINE, settings)

    assert script.hook
    assert "Flipkart" in script.hook
    assert "Associate Software Engineer" in script.hook
    assert "apply soon" in script.hook.lower()
    assert script.on_screen.stipend == ""
    assert script.on_screen.deadline_badge == "Apply soon"
    assert len(script.title) <= 100
    assert CARD_JOB_NO_DEADLINE["apply_url"] in script.description


def test_template_fallback_hackathon():
    """Test template fallback for hackathon."""
    settings = load_shorts_settings()
    script = _template_fallback(CARD_HACKATHON, settings)

    assert script.hook
    assert "Government of India" in script.hook or "Smart India Hackathon" in script.hook
    assert script.on_screen.stipend == "Prize pool ₹10 lakh"
    assert "2026" in script.on_screen.eligibility
    assert "#Hackathon" in script.hashtags or "#hackathon" in script.description.lower()


def test_word_count():
    """Test word count function."""
    assert count_words("Hello world") == 2
    assert count_words("This is a test") == 4
    assert count_words("") == 0


def test_script_validation_internship():
    """Test validation passes for internship script."""
    settings = load_shorts_settings()
    script = _template_fallback(CARD_INTERNSHIP_WITH_STIPEND, settings)
    is_valid, errors = validate_script(script, CARD_INTERNSHIP_WITH_STIPEND)

    # Template fallback should produce valid scripts
    # Word count may vary slightly but should be reasonable
    assert is_valid, f"Validation failed: {errors}"


def test_script_validation_job_no_deadline():
    """Test validation for job without deadline."""
    settings = load_shorts_settings()
    script = _template_fallback(CARD_JOB_NO_DEADLINE, settings)
    is_valid, errors = validate_script(script, CARD_JOB_NO_DEADLINE)

    # Should not mention specific dates
    date_errors = [e for e in errors if "date" in e.lower()]
    assert len(date_errors) == 0, f"Should not mention dates: {date_errors}"


def test_script_validation_hackathon():
    """Test validation for hackathon script."""
    settings = load_shorts_settings()
    script = _template_fallback(CARD_HACKATHON, settings)
    is_valid, errors = validate_script(script, CARD_HACKATHON)

    # Should have hackathon-specific hashtags
    assert is_valid, f"Validation failed: {errors}"


def test_generate_script_template_mode():
    settings = load_shorts_settings()
    settings['llm']['provider'] = 'template'
    assert generate_script(CARD_INTERNSHIP_WITH_STIPEND, settings).on_screen.company == 'Google'


def test_script_serialization():
    """Test ScriptDoc to_dict and from_dict roundtrip."""
    settings = load_shorts_settings()
    script = _template_fallback(CARD_INTERNSHIP_WITH_STIPEND, settings)
    script_dict = script.to_dict()
    script2 = script.__class__.from_dict(script_dict)

    assert script.hook == script2.hook
    assert len(script.voiceover_lines) == len(script2.voiceover_lines)
    assert script.on_screen.company == script2.on_screen.company
    assert script.title == script2.title


def test_ollama_request_and_response(monkeypatch):
    import json
    from unittest.mock import Mock
    settings = load_shorts_settings()
    expected = _template_fallback(CARD_INTERNSHIP_WITH_STIPEND, settings)
    response = Mock()
    response.json.return_value = {'message': {'content': json.dumps(expected.to_dict())}}
    post = Mock(return_value=response)
    monkeypatch.setattr('requests.post', post)
    result = generate_script(CARD_INTERNSHIP_WITH_STIPEND, settings)
    assert result.title == expected.title
    assert post.call_args.args[0].endswith('/api/chat')
    body = post.call_args.kwargs['json']
    assert body['format'] == 'json' and body['stream'] is False and body['think'] is False
    assert body['keep_alive'] == 0
    assert 'Authorization' not in post.call_args.kwargs


def test_ollama_cannot_replace_structured_listing_facts(monkeypatch):
    import json
    from unittest.mock import Mock
    settings = load_shorts_settings()
    payload = _template_fallback(CARD_INTERNSHIP_WITH_STIPEND, settings).to_dict()
    payload['on_screen']['stipend'] = 'Rs 999,999 per month'
    payload['description'] = 'https://unofficial.example/apply'
    response = Mock()
    response.json.return_value = {'message': {'content': json.dumps(payload)}}
    monkeypatch.setattr('requests.post', Mock(return_value=response))
    script = generate_script(CARD_INTERNSHIP_WITH_STIPEND, settings)
    assert script.on_screen.stipend == CARD_INTERNSHIP_WITH_STIPEND['stipend']
    assert script.description.splitlines()[0] == CARD_INTERNSHIP_WITH_STIPEND['apply_url']
    assert len(script.hashtags) == len(set(script.hashtags))


def test_invalid_ollama_facts_retry_then_fail(monkeypatch):
    import json
    from unittest.mock import Mock
    settings = load_shorts_settings()
    script = _template_fallback(CARD_INTERNSHIP_WITH_STIPEND, settings)
    script.voiceover_lines[1].text += ' Salary Rs 999,999 per month.'
    response = Mock()
    response.json.return_value = {'message': {'content': json.dumps(script.to_dict())}}
    post = Mock(return_value=response)
    monkeypatch.setattr('requests.post', post)
    with pytest.raises(RuntimeError, match='Ollama'):
        generate_script(CARD_INTERNSHIP_WITH_STIPEND, settings)
    assert post.call_count == settings['llm']['max_retries']


def test_ollama_unavailable_does_not_silently_publish_templates(monkeypatch):
    import requests
    from unittest.mock import Mock
    settings = load_shorts_settings()
    monkeypatch.setattr('requests.post', Mock(side_effect=requests.ConnectionError('offline')))
    with pytest.raises(RuntimeError):
        generate_script(CARD_INTERNSHIP_WITH_STIPEND, settings)
    settings['llm']['fallback_on_failure'] = True
    assert generate_script(CARD_INTERNSHIP_WITH_STIPEND, settings).on_screen.company == 'Google'
