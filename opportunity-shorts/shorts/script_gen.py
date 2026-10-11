from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

from .models import ScriptDoc, OnScreenText, VoiceoverLine
from .settings import load_shorts_settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a script writer for YouTube Shorts about internships and jobs for Indian students.
Write a 20-35 second script (55-85 words) in simple Indian English.
Rules:
- Hook in first 2 seconds: "Company role, apply by [deadline/soon]"
- Use ONLY facts from the card. Never invent stipend, deadline, eligibility, company, or links.
- If a field is empty/null, omit it. Never say a date if deadline is missing.
- End with "Apply link is in the description."
- Keep it conversational and clear for college students.
- Optional: light Hinglish in Latin script if enabled (e.g. "Good for 2027 batch, apply kar do").
"""

USER_PROMPT_TEMPLATE = """Write a script for this opportunity card (JSON format only):
{card_json}

Return JSON with this exact structure:
{{
  "hook": "2-second hook",
  "voiceover_lines": [
    {{"text": "line 1"}},
    {{"text": "line 2"}}
  ],
  "on_screen": {{
    "role": "exact role from card",
    "company": "exact company from card",
    "location": "location from card or empty",
    "stipend": "stipend from card or empty",
    "eligibility": "batch years or experience from card or empty",
    "deadline_badge": "deadline urgency or 'Apply soon'",
    "cta": "Apply link in description"
  }},
  "title": "YouTube title (max 100 chars)",
  "description": "Line 1: apply URL\\nLine 2+: role/company/eligibility/deadline\\nAlways verify details on the official site\\n#hashtags including #Shorts",
  "hashtags": ["#Internship", "#Shorts", ...]
}}"""


def _template_fallback(card: dict, settings: dict) -> ScriptDoc:
    """Deterministic template fallback when LLM is unavailable."""
    company = card.get("company", "")
    role = card.get("role", "")
    location = card.get("location", "")
    stipend = card.get("stipend", "")
    deadline = card.get("deadline")
    batch_years = card.get("batch_years", [])
    experience = card.get("experience", "")
    apply_url = card.get("apply_url", "")
    opp_type = card.get("type", "job")

    # Build deadline badge
    if deadline:
        try:
            d = datetime.strptime(deadline, "%Y-%m-%d")
            deadline_badge = f"Apply by {d.strftime('%d %b')}"
        except:
            deadline_badge = "Apply soon"
    else:
        deadline_badge = "Apply soon"

    # Build eligibility text (simplify for hackathons with many years)
    eligibility_parts = []
    if batch_years:
        if len(batch_years) > 2:
            eligibility_parts.append(f"{', '.join(str(y) for y in batch_years)} batch")
        else:
            eligibility_parts.append(f"{', '.join(str(y) for y in batch_years)} batch")
    if experience:
        eligibility_parts.append(experience)
    eligibility = ", ".join(eligibility_parts) if eligibility_parts else ""

    # Build hook
    hook_parts = [company, role]
    if deadline:
        hook_parts.append(f"apply by {deadline_badge.replace('Apply by ', '')}")
    else:
        hook_parts.append("apply soon")
    hook = ", ".join(hook_parts) + "."

    # Build voiceover lines (simple template, concise)
    lines = []
    lines.append(f"{hook}")
    if location:
        lines.append(f"Location: {location}.")
    if stipend:
        lines.append(f"Stipend: {stipend}.")
    if eligibility:
        lines.append(f"Open to {eligibility}.")
    lines.append("Check the official listing carefully for the full requirements and application steps. Review the details before you apply, and make sure this opportunity matches what you are looking for.")
    lines.append("Apply link is in the description.")
    if len(' '.join(lines).split()) < settings['script']['min_words']:
        lines.insert(-1, 'Read the responsibilities carefully and prepare your application using the instructions provided there.')

    voiceover_lines = [VoiceoverLine(text=line) for line in lines]

    # Build on-screen text
    on_screen = OnScreenText(
        role=role,
        company=company,
        location=location,
        stipend=stipend,
        eligibility=eligibility,
        deadline_badge=deadline_badge,
        cta="Apply link in description",
    )

    # Build title
    title = f"{role} at {company}"
    if len(title) > 100:
        title = title[:97] + "..."

    # Build description (keep concise)
    desc_lines = [apply_url]
    desc_lines.append(f"{role} at {company}")
    from .trust import is_promoted
    if is_promoted(card):
        desc_lines.append('Promoted listing')
    if location:
        desc_lines.append(f"Location: {location}")
    if stipend:
        desc_lines.append(f"Stipend: {stipend}")
    if eligibility:
        desc_lines.append(f"Eligibility: {eligibility}")
    if deadline:
        desc_lines.append(f"Deadline: {deadline}")
    desc_lines.append("Always verify details on the official site")
    desc_lines.append(f"#{opp_type.capitalize()} #Shorts #India")
    description = "\n".join(desc_lines)

    # Build hashtags (keep minimal)
    hashtags = [f"#{opp_type.capitalize()}", "#Shorts", "#India"]
    if "internship" in opp_type.lower():
        hashtags.append("#Internship")
    if "hackathon" in opp_type.lower():
        hashtags.append("#Hackathon")

    return ScriptDoc(
        hook=hook,
        voiceover_lines=voiceover_lines,
        on_screen=on_screen,
        title=title,
        description=description,
        hashtags=hashtags,
    )


def generate_script(card: dict, settings: Optional[dict] = None) -> ScriptDoc:
    """Generate a ScriptDoc from a card using Anthropic API, with template fallback."""
    settings = settings or load_shorts_settings()
    api_key = settings.get("anthropic_api_key")

    if not api_key:
        logger.warning("No Anthropic API key found, using template fallback")
        return _template_fallback(card, settings)

    try:
        import anthropic
    except ImportError:
        logger.warning("anthropic package not installed, using template fallback")
        return _template_fallback(card, settings)

    client = anthropic.Anthropic(api_key=api_key)
    model = settings["llm"]["model"]
    temperature = settings["llm"]["temperature"]
    max_retries = settings["llm"]["max_retries"]
    timeout = settings["llm"]["timeout_seconds"]

    card_json = json.dumps(card, ensure_ascii=False)
    prompt = USER_PROMPT_TEMPLATE.format(card_json=card_json)

    for attempt in range(max_retries):
        try:
            sampling = {'temperature': temperature} if temperature is not None else {}
            response = client.messages.create(
                model=model,
                max_tokens=2000,
                **sampling,
                extra_body=settings['llm'].get('extra_body', {}),
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
                timeout=timeout,
            )
            content = ''.join(block.text for block in response.content if getattr(block, 'type', 'text') == 'text')
            # Extract JSON from response (in case there's extra text)
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            data = json.loads(content)
            script = ScriptDoc.from_dict(data)
            from .validate_script import validate_script
            valid, errors = validate_script(script, card)
            if not valid:
                raise ValueError("; ".join(errors))
            return script
        except (ValueError, TypeError, KeyError, anthropic.APIError) as e:
            logger.warning(f"LLM attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                logger.warning("All LLM attempts failed, using template fallback")
                return _template_fallback(card, settings)
    return _template_fallback(card, settings)


def count_words(text: str) -> int:
    """Count words in text (simple split by whitespace)."""
    return len(text.split())
