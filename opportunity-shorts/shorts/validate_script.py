"""Conservative fact validation; unrestricted prose still requires human review."""
from __future__ import annotations
import re
from datetime import datetime
from .models import ScriptDoc


class ValidationError(ValueError):
    pass


def extract_numbers(text):
    return re.findall(r'\d+(?:[, .]\d+)*', text)


def extract_dates(text):
    # Application URL IDs are not prose dates; URLs are checked separately.
    text = re.sub(r'https?://[^\s]+', '', text)
    month = r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
    return re.findall(r'\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}/\d{4}\b|'
        + rf'\b\d{{1,2}}[ \t]+{month}\b(?:[ \t]+\d{{4}}\b)?|\b{month}[ \t]+\d{{1,2}}\b(?:,?[ \t]+\d{{4}}\b)?', text, re.I)


def extract_urls(text):
    return re.findall(r'https?://[^\s]+', text)


def extract_batch_years(text):
    return re.findall(r'\d{4}\s+batch|batch\s+\d{4}', text, re.I)


def validate_script(script: ScriptDoc, card: dict):
    errors = []
    from .trust import is_promoted, promoted_script
    if is_promoted(card) != promoted_script(script):
        errors.append('Promoted listing disclosure must match source designation')
    spoken = ' '.join(line.text for line in script.voiceover_lines)
    count = len(spoken.split())
    if not 45 <= count <= 110:
        errors.append(f'Spoken word count {count} outside range [45, 110]')
    text = ' '.join([script.hook, spoken, script.title, script.description,
                     *vars(script.on_screen).values(), *script.hashtags])
    evidence = ' '.join(str(card.get(key) or '') for key in
        ('company', 'role', 'location', 'stipend', 'batch_years', 'experience', 'deadline', 'apply_url'))
    allowed_dates = []
    if card.get('deadline'):
        try:
            date = datetime.strptime(card['deadline'], '%Y-%m-%d')
            allowed_dates = [date.strftime(fmt) for fmt in ('%d %b', '%d %B', '%b %d', '%B %d',
                '%d %b %Y', '%d %B %Y', '%b %d %Y', '%B %d %Y', '%b %d, %Y', '%B %d, %Y', '%d/%m/%Y')]
            allowed_dates.append(card['deadline'])
            evidence += ' ' + ' '.join(allowed_dates)
        except ValueError:
            errors.append('Card deadline must be YYYY-MM-DD')
    # Compare complete numeric tokens, not substrings (e.g. 8000 is not 80000).
    numbers = lambda value: set(re.findall(r'\d+(?:,\d{3})*(?:\.\d+)?', value))
    unsupported = numbers(text) - numbers(evidence)
    if unsupported:
        errors.append(f'Unsupported numbers: {sorted(unsupported)}')
    for amount in re.findall(r'(?:\b(?:Rs\.?|INR|USD|EUR|GBP)\s*|[₹$€£]\s*)\d[\d,]*(?:\.\d+)?(?:\s*(?:lakh|lpa|k))?', text, re.I):
        normalize = lambda value: re.sub(r'\s+', '', value).casefold()
        if normalize(amount) not in normalize(card.get('stipend') or ''):
            errors.append(f'Unsupported compensation amount or currency: {amount}')
    for date in extract_dates(text):
        if date.casefold() not in [d.casefold() for d in allowed_dates]:
            errors.append(f'Unsupported date: {date}')
    weekdays = re.findall(r'\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b', text, re.I)
    for day in weekdays:
        if not card.get('deadline') or day.casefold() != datetime.strptime(card['deadline'], '%Y-%m-%d').strftime('%A').casefold():
            errors.append(f'Unsupported weekday: {day}')
    for field in ('company', 'role', 'location', 'stipend'):
        value = getattr(script.on_screen, field)
        if value and value != (card.get(field) or ''):
            errors.append(f'On-screen {field} does not match card')
    expected_eligibility = []
    if card.get('batch_years'):
        expected_eligibility.append(', '.join(str(y) for y in card['batch_years']) + ' batch')
    if card.get('experience'):
        expected_eligibility.append(card['experience'])
    if script.on_screen.eligibility != ', '.join(expected_eligibility):
        errors.append('Eligibility must match card batch years and experience')
    if not card.get('stipend') and re.search(r'\b(?:stipend|salary|paid|unpaid|lakh|rupees)\b|[₹$]', spoken, re.I):
        errors.append('Script mentions compensation but card has none')
    if not card.get('deadline') and script.on_screen.deadline_badge.casefold() != 'apply soon':
        errors.append('Unknown deadline must say Apply soon')
    urls = extract_urls(text)
    if any(url != card.get('apply_url') for url in urls):
        errors.append('Script contains an unofficial URL')
    if not script.description.splitlines() or script.description.splitlines()[0] != card.get('apply_url'):
        errors.append('Description must start with the exact official application URL')
    if len(script.title) > 100:
        errors.append('Title exceeds 100 characters')
    if 'official site' not in script.description.lower():
        errors.append('Description missing official site disclaimer')
    if '#Shorts' not in script.description:
        errors.append('Description missing #Shorts')
    if not script.hook.strip():
        errors.append('Hook is empty')
    if not script.voiceover_lines or 'apply link is in the description' not in script.voiceover_lines[-1].text.lower():
        errors.append('Voiceover must end with the apply-link CTA')
    return not errors, errors
