"""Text cleaning and fact extraction. Pure functions, no network, easy to unit test."""
from __future__ import annotations

import html
import re
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

from bs4 import BeautifulSoup

# ---------------------------------------------------------------- text

def html_to_text(raw: str) -> str:
    """HTML (possibly entity-escaped, as Greenhouse returns it) -> readable plain text."""
    if not raw:
        return ""
    if "&lt;" in raw and "<" not in raw:
        raw = html.unescape(raw)
    soup = BeautifulSoup(raw, "html.parser")
    for li in soup.find_all("li"):
        li.insert_before("\n- ")
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for tag in soup.find_all(["p", "div", "h1", "h2", "h3", "h4", "ul", "ol"]):
        tag.insert_after("\n")
    text = soup.get_text()
    text = html.unescape(text).replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


# ---------------------------------------------------------------- dates

def to_iso_utc(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_any_datetime(value) -> Optional[str]:
    """ISO strings, RFC-2822 (RSS), epoch seconds or milliseconds -> ISO-8601 UTC, else None."""
    if value in (None, "", 0):
        return None
    try:
        if isinstance(value, (int, float)):
            v = float(value)
            if v > 1e11:      # milliseconds
                v /= 1000.0
            return to_iso_utc(datetime.fromtimestamp(v, tz=timezone.utc))
        s = str(value).strip()
        if s.isdigit():
            return parse_any_datetime(int(s))
        try:
            return to_iso_utc(datetime.fromisoformat(s.replace("Z", "+00:00")))
        except ValueError:
            return to_iso_utc(parsedate_to_datetime(s))
    except (ValueError, TypeError, OverflowError, OSError):
        return None


MONTHS = {}
for _i, _names in enumerate([("jan", "january"), ("feb", "february"), ("mar", "march"), ("apr", "april"),
                             ("may",), ("jun", "june"), ("jul", "july"), ("aug", "august"),
                             ("sep", "sept", "september"), ("oct", "october"), ("nov", "november"),
                             ("dec", "december")], start=1):
    for _n in _names:
        MONTHS[_n] = _i

_DEADLINE_KW = re.compile(
    r"(?:last\s+date(?:\s+to\s+(?:apply|register))?|deadline(?:\s+to\s+apply)?|closing\s+date|"
    r"apply\s+(?:by|before|until|till)|(?:applications?|registrations?|entries)\s+(?:close|closes|closing|end|ends|due)(?:\s+on)?|"
    r"register\s+(?:by|before)|submit\s+(?:by|before))", re.I)

_MON = r"([A-Za-z]{3,9})\.?"
_DATE_PATTERNS = [
    ("dmy_text", re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?[\s\-/]+{_MON}[\s,\-/]+(\d{{4}})\b")),
    ("mdy_text", re.compile(rf"\b{_MON}\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})\b")),
    ("iso", re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")),
    ("numeric", re.compile(r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})\b")),
    ("dm_text", re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+{_MON}(?![\w,]*\s*\d{{4}})")),
]


def _build_date(kind: str, g: tuple, today: date) -> Optional[date]:
    try:
        if kind == "dmy_text":
            d, mon, y = int(g[0]), MONTHS.get(g[1].lower()), int(g[2])
        elif kind == "mdy_text":
            mon, d, y = MONTHS.get(g[0].lower()), int(g[1]), int(g[2])
        elif kind == "iso":
            y, mon, d = int(g[0]), int(g[1]), int(g[2])
        elif kind == "numeric":          # Indian convention DD/MM/YYYY
            d, mon, y = int(g[0]), int(g[1]), int(g[2])
            if mon > 12 and d <= 12:
                d, mon = mon, d
        else:                            # dm_text: no year -> next occurrence
            d, mon = int(g[0]), MONTHS.get(g[1].lower())
            if not mon:
                return None
            y = today.year
            cand = date(y, mon, d)
            if cand < today - timedelta(days=30):
                y += 1
        if not mon:
            return None
        out = date(y, mon, d)
        return out if today.year - 1 <= out.year <= today.year + 2 else None
    except (ValueError, TypeError):
        return None


def extract_deadline(text: str, today: Optional[date] = None) -> Optional[str]:
    """Find 'apply by / last date / deadline ...' followed by a date. Returns YYYY-MM-DD or None."""
    if not text:
        return None
    today = today or date.today()
    for m in _DEADLINE_KW.finditer(text):
        window = text[m.end(): m.end() + 70]
        cands = []
        for kind, pat in _DATE_PATTERNS:
            for pm in pat.finditer(window):
                d = _build_date(kind, pm.groups(), today)
                if d:
                    cands.append((pm.start(), d))
        if cands:
            return min(cands, key=lambda c: c[0])[1].isoformat()
    return None


# ---------------------------------------------------------------- money / eligibility

_AMT = (r"(?:₹|Rs\.?|INR)\s?\d[\d,]*(?:\.\d+)?\s?(?:k|K|L|lakhs?|LPA|lpa)?"
        r"(?:\s?(?:-|–|to)\s?(?:₹|Rs\.?|INR)?\s?\d[\d,]*(?:\.\d+)?\s?(?:k|K|L|lakhs?|LPA|lpa)?)?"
        r"(?:\s?(?:/|per)\s?(?:month|mo|year|annum|yr|week))?")
_AMT_RE = re.compile(_AMT)
_PAY_KW = re.compile(r"stipend|salary|ctc|compensation|\bpay\b|remuneration", re.I)


def extract_stipend(text: str) -> str:
    if not text:
        return ""
    for m in _AMT_RE.finditer(text):
        before = text[max(0, m.start() - 100): m.start()]
        if _PAY_KW.search(before):
            return m.group(0).strip()
    return ""


_BATCH_KW = re.compile(r"batch(?:es)?|graduat\w*|pass(?:ing|ed)?[\s\-]*out|class\s+of", re.I)


def extract_batch_years(text: str, current_year: Optional[int] = None) -> list:
    """Graduation/batch years mentioned near 'batch / graduating / pass-out'. Dates that carry a year
    (e.g. a deadline '25 October 2026') are blanked out first so they aren't mistaken for batches."""
    if not text:
        return []
    cy = current_year or date.today().year
    for kind, pat in _DATE_PATTERNS:
        if kind != "dm_text":
            text = pat.sub(" ", text)
    years = set()
    for m in _BATCH_KW.finditer(text):
        window = text[max(0, m.start() - 30): m.end() + 30]
        for y in re.findall(r"\b(20[2-3]\d)\b", window):
            if cy - 1 <= int(y) <= cy + 5:
                years.add(int(y))
    return sorted(years)


_EXP_RE = re.compile(r"(\d{1,2})\s*(\+|(?:-|–|to)\s*(\d{1,2}))?\s*(?:years?|yrs?)\b", re.I)


def extract_experience(text: str) -> str:
    if not text:
        return ""
    for m in _EXP_RE.finditer(text):
        before = re.split(r'[\n.;!?]', text[max(0, m.start() - 60):m.start()])[-1]
        after = re.split(r'[\n.;!?]', text[m.end():m.end() + 80])[0]
        # Academic duration is not required work experience merely because
        # "experience" appears nearby in an alternative qualification.
        if re.match(r'\s*(?:of\s+)?(?:university|college|school|education|study|studies|degree)\b', after, re.I):
            continue
        following = re.match(r'\s*(?:of\s+)?(?:[\w-]+\s+){0,5}experience\b', after, re.I)
        preceding = re.search(r'\bexperience(?:\s+required)?\s*[:=-]?\s*(?:of\s+)?$', before, re.I)
        if not following and not preceding:
            continue
        lo, plus, hi = m.group(1), m.group(2), m.group(3)
        if hi:
            return f"{lo}-{hi} years"
        if plus == "+":
            return f"{lo}+ years"
        return f"{lo} years"
    if re.search(r"\bfreshers?\b", text, re.I):
        return "Freshers welcome"
    return ""


# ---------------------------------------------------------------- location / type

INDIA_TERMS = [
    "india", "bengaluru", "bangalore", "hyderabad", "pune", "mumbai", "navi mumbai", "delhi",
    "new delhi", "gurgaon", "gurugram", "noida", "greater noida", "chennai", "kolkata", "ahmedabad",
    "kochi", "cochin", "coimbatore", "jaipur", "chandigarh", "mohali", "indore", "thiruvananthapuram",
    "trivandrum", "bhubaneswar", "nagpur", "lucknow", "vadodara", "visakhapatnam", "mysuru", "mysore",
    "pan india", "ncr", "dewas",
]
_INDIA_RE = re.compile(r"\b(?:" + "|".join(re.escape(t) for t in INDIA_TERMS) + r")\b", re.I)
_REMOTE_RE = re.compile(r"\bremote\b|work\s+from\s+home|\bwfh\b|\banywhere\b|\bworldwide\b", re.I)


def detect_location(loc: str) -> tuple:
    """-> (is_india, is_remote) from free-text location."""
    if not loc:
        return False, False
    return bool(_INDIA_RE.search(loc)), bool(_REMOTE_RE.search(loc))


def classify_type(title: str) -> str:
    t = (title or "").lower()
    if re.search(r"\bintern(s|ship|ships)?\b", t):
        return "internship"
    if "hackathon" in t or "buildathon" in t:
        return "hackathon"
    if "fellowship" in t:
        return "fellowship"
    if "scholarship" in t:
        return "scholarship"
    return "job"


# ---------------------------------------------------------------- enrichment

def enrich(opp, today: Optional[date] = None, max_desc: int = 6000):
    """Fill derived fields in place: location flags, deadline, stipend, batch, experience, type."""
    today = today or date.today()
    full = (opp.description or "").strip()
    ind, rem = detect_location(opp.location)
    opp.is_india = bool(opp.is_india or ind)
    opp.is_remote = bool(opp.is_remote or rem)
    if not opp.deadline:
        opp.deadline = extract_deadline(full, today)
    if not opp.stipend_text:
        opp.stipend_text = extract_stipend(full)
    if not opp.batch_years:
        opp.batch_years = extract_batch_years(f"{opp.title}\n{full}", today.year)
    if not opp.experience_text:
        opp.experience_text = extract_experience(full)
    if opp.opp_type == "job":
        opp.opp_type = classify_type(opp.title)
    opp.description = full[:max_desc]
    return opp
