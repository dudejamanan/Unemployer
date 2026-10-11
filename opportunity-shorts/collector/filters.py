from __future__ import annotations

import re

EARLY_TITLE_RE = re.compile(
    r"\b(intern|interns|internship|trainee|apprentice|apprenticeship|graduate|new[\s\-]?grad|fresher|"
    r"freshers|entry[\s\-]level|junior|campus|university|early[\s\-]career|sde[\s\-]?1|"
    r"associate software engineer|co[\s\-]?op|student|summer analyst)\b", re.I)
EARLY_DESC_RE = re.compile(r"\bfreshers?\b|\bnew\s+grads?\b|\b0\s*(?:-|–|to)\s*[12]\s*years?\b", re.I)


SCAM_RE = re.compile(
    r"registration\s+fee|security\s+deposit|refundable\s+deposit|processing\s+fee|training\s+fee|"
    r"pay\s+(?:to|for)\s+(?:apply|join|register)|(?:whatsapp|telegram)\s+(?:only|us\s+at)|"
    r"earn\s+\u20b9?\s?\d[\d,]*\s*(?:per|/)\s*day|work\s+from\s+home\s+and\s+earn", re.I)


def looks_scammy(opp) -> bool:
    """Pay-to-apply / fee / messaging-app-only patterns common in fake internship posts."""
    return bool(SCAM_RE.search(f"{opp.title}\n{opp.description}"))


def _kw_regex(words):
    words = [w.strip() for w in (words or []) if w and w.strip()]
    if not words:
        return None
    return re.compile(r"\b(?:" + "|".join(re.escape(w) for w in words) + r")\b", re.I)


def is_early_career(opp) -> bool:
    if opp.opp_type in ("internship", "hackathon", "fellowship", "scholarship"):
        return True
    if EARLY_TITLE_RE.search(opp.title or ""):
        return True
    exp = opp.experience_text or ""
    if exp.lower().startswith("fresher"):
        return True
    nums = [int(n) for n in re.findall(r"\d+", exp)]
    if nums and "+" not in exp and max(nums) <= 2:
        return True
    return bool(EARLY_DESC_RE.search((opp.description or "")[:2000]))


def india_eligibility(opp):
    """Conservative evidence of applicant eligibility, distinct from job location.

    Remote alone does not establish worldwide hiring. Explicit exclusions take
    precedence over worldwide or India wording. Citizenship and visa conditions
    still require human verification before publishing a listing.
    """
    location = opp.location or ''
    text = f'{location}\n{opp.description or ""}'
    if re.search(r'\b(?:excluding|except|not (?:available|open|hiring) (?:in|to))\s+(?:(?:applicants|candidates|students) (?:from|in)\s+)?India\b', text, re.I):
        return False, 'India is explicitly excluded'
    if opp.is_india:
        return True, 'Role is located in India'
    if opp.is_remote and re.search(r'\b(?:worldwide|anywhere|globally|global|all countries|Asia|APAC)\b', location, re.I):
        if re.search(r'\b(?:US|USA|United States|UK|EU|Europe|Canada|Australia)\s+only\b', text, re.I):
            return False, 'Restricted applicant location'
        return True, 'Remote applicant region includes India'
    if re.search(r'\b(?:open|available)\s+to\s+(?:applicants|candidates|students)\s+(?:of|from|in)\s+(?:all (?:nationalities|countries)|India)\b', text, re.I):
        if re.search(r'\b(?:US|USA|United States|UK|EU|Europe|Canada|Australia)\s+(?:citizens|residents)\s+only\b|\bmust\s+(?:already\s+)?(?:be\s+)?(?:legally\s+)?(?:authorized|authorised|eligible)\s+to\s+work\s+in\s+(?:the\s+)?(?:US|USA|United States|UK|Canada|Australia)\b', text, re.I):
            return False, 'Restricted nationality or residence'
        return True, 'Description explicitly accepts Indian or international applicants'
    return False, 'Indian applicant eligibility is not established'


def passes(opp, cfg: dict):
    """-> (keep: bool, reason: str). Manual / verified items skip these filters in the pipeline."""
    if looks_scammy(opp):
        return False, "suspicious"
    if cfg.get('india_eligible_only', False):
        if not india_eligibility(opp)[0]:
            return False, 'not_india_eligible'
    elif cfg.get("india_only", True):
        if not (opp.is_india or (cfg.get("allow_global_remote") and opp.is_remote)):
            return False, "not_india"
    if cfg.get("mode", "early_career") == "early_career" and not is_early_career(opp):
        return False, "not_early_career"
    if opp.opp_type != "internship":
        ex = _kw_regex(cfg.get("exclude_title_keywords"))
        if ex and ex.search(opp.title or ""):
            return False, "excluded_title"
    inc = _kw_regex(cfg.get("include_title_keywords"))
    if inc and not inc.search(opp.title or ""):
        return False, "title_keyword_miss"
    if len(opp.description or "") < int(cfg.get("min_description_chars", 0)):
        return False, "stub_posting"
    return True, "ok"
