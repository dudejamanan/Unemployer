from datetime import date

from collector.normalize import (classify_type, detect_location, extract_batch_years, extract_deadline,
                                 extract_experience, extract_stipend, html_to_text, parse_any_datetime)

TODAY = date(2026, 10, 5)


def test_academic_year_is_not_required_work_experience():
    assert extract_experience('At least 1 year of university education, or equivalent work experience.') == ''
    assert extract_experience('A 4 year degree. Previous internship experience is helpful.') == ''
    assert extract_experience('At least 2 years of professional software development experience.') == '2 years'
    assert extract_experience('Experience required: 0-2 years') == '0-2 years'
    assert extract_experience('2+ years experience with Python') == '2+ years'


def test_html_to_text_handles_escaped_greenhouse_html():
    out = html_to_text("&lt;p&gt;Hello &amp;amp; welcome&lt;/p&gt;&lt;ul&gt;&lt;li&gt;One&lt;/li&gt;&lt;li&gt;Two&lt;/li&gt;&lt;/ul&gt;")
    assert "Hello & welcome" in out and "- One" in out and "- Two" in out and "<" not in out


def test_parse_datetimes():
    assert parse_any_datetime("2026-10-01T10:00:00-04:00") == "2026-10-01T14:00:00Z"
    assert parse_any_datetime(1790000000000).startswith("2026-")
    assert parse_any_datetime("Mon, 05 Oct 2026 06:00:00 GMT") == "2026-10-05T06:00:00Z"
    assert parse_any_datetime("garbage") is None and parse_any_datetime(None) is None


def test_deadline_variants():
    assert extract_deadline("Last date to apply: 15 October 2026", TODAY) == "2026-10-15"
    assert extract_deadline("Apply by Oct 20th, 2026 please", TODAY) == "2026-10-20"
    assert extract_deadline("Deadline: 12/11/2026", TODAY) == "2026-11-12"          # DD/MM
    assert extract_deadline("Applications close on 2026-12-01.", TODAY) == "2026-12-01"
    assert extract_deadline("Registrations close on 20 Oct 2026.", TODAY) == "2026-10-20"
    assert extract_deadline("apply by 25 Oct", TODAY) == "2026-10-25"               # no year
    assert extract_deadline("apply by 5 January", TODAY) == "2027-01-05"            # rolls to next year


def test_deadline_false_positives():
    assert extract_deadline("apply by 5 years of experience marketing", TODAY) is None
    assert extract_deadline("We were founded on 3 March 2015.", TODAY) is None
    assert extract_deadline("", TODAY) is None


def test_stipend():
    assert "25,000" in extract_stipend("Stipend: ₹25,000 per month plus perks")
    assert extract_stipend("Stipend: Rs 4 LPA").startswith("Rs 4")
    assert extract_stipend("Our office costs ₹25,000 to rent") == ""      # no pay keyword nearby


def test_batch_years():
    assert extract_batch_years("Open to 2027 batch and 2028 graduates", 2026) == [2027, 2028]
    assert extract_batch_years("Founded in 2021, batch 2099", 2026) == []
    assert extract_batch_years("Open to 2027 batch graduates. Last date to apply: 25 October 2026.", 2026) == [2027]
    assert extract_batch_years("2026 pass-outs welcome", 2026) == [2026]


def test_experience():
    assert extract_experience("0-2 years of experience preferred") == "0-2 years"
    assert extract_experience("Minimum 5+ years experience") == "5+ years"
    assert extract_experience("Freshers can apply") == "Freshers welcome"
    assert extract_experience("We have been around for 10 years") == ""


def test_location_detection():
    assert detect_location("Bengaluru, India") == (True, False)
    assert detect_location("Remote - India") == (True, True)
    assert detect_location("Remote (US)") == (False, True)
    assert detect_location("Indianapolis, IN") == (False, False)
    assert detect_location("") == (False, False)


def test_classify_type():
    assert classify_type("Summer Intern - ML") == "internship"
    assert classify_type("Hack for Bharat Hackathon") == "hackathon"
    assert classify_type("Internal Tools Engineer") == "job"
