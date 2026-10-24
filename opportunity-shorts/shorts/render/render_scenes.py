from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..models import ScriptDoc
from ..settings import load_shorts_settings

logger = logging.getLogger(__name__)

# Scene templates
SCENE_TEMPLATES = {
    "hook": "hook_scene.html",
    "facts": "facts_scene.html",
    "role": "role_scene.html",
    "guide": "guide_scene.html",
    "deadline": "deadline_scene.html",
    "cta": "cta_scene.html",
}

# Layout rotation sequence (scene types in order)
LAYOUT_SEQUENCE = ["hook", "facts", "role", "deadline", "cta"]


def _get_template_dir(settings: dict) -> Path:
    """Get directory containing HTML templates."""
    project_root = Path(__file__).parent.parent.parent
    return project_root / "shorts" / "render" / "templates"


def _get_theme(settings: dict, theme_index: int) -> dict:
    """Get color theme by index (rotates through available themes)."""
    themes = settings["theme"]["color_schemes"]
    return themes[theme_index % len(themes)]


def _extract_domain(url: str) -> str:
    """Extract domain from URL for display."""
    try:
        parsed = urlparse(url)
        return parsed.netloc.replace("www.", "")
    except:
        return url


def cover_compensation(text):
    """Presentation-only INR formatting; preserve qualifiers and ranges."""
    import re
    from decimal import Decimal
    match = re.fullmatch(r'\s*(up to\s+)?(?:INR|Rs\.?|₹)\s*(\d[\d,]*(?:\.\d+)?)(?:\s*[-–]\s*(\d[\d,]*(?:\.\d+)?))?\s*(?:/|per)?\s*(month|monthly|year|yearly|annum)\s*', text or '', re.I)
    if not match:
        return text or '', ''
    qualifier, low, high, period = match.groups()
    amount = ('Up to ' if qualifier else '') + '₹' + format(Decimal(low.replace(',', '')), ',')
    if high:
        amount += '–' + format(Decimal(high.replace(',', '')), ',')
    return amount, 'per month' if period.lower() in ('month', 'monthly') else 'per year'


def render_scene(
    scene_type: str,
    script: ScriptDoc,
    theme: dict,
    output_path: Path,
    apply_url: str = "",
    settings: Optional[dict] = None
) -> Path:
    """
    Render a single scene to an image using Playwright.

    Args:
        scene_type: Type of scene (hook, facts, deadline, cta)
        script: ScriptDoc containing on-screen text
        theme: Color theme dict
        output_path: Path where to save the rendered image
        apply_url: Application URL for domain extraction
        settings: Settings dict

    Returns:
        Path to rendered image
    """
    settings = settings or load_shorts_settings()
    template_dir = _get_template_dir(settings)

    # Load template
    template_file = template_dir / SCENE_TEMPLATES[scene_type]
    template = Environment(loader=FileSystemLoader(str(template_dir)),
                           autoescape=select_autoescape(['html'])).get_template(template_file.name)
    import base64
    font_css = ''
    fonts = list(Path(settings['paths']['fonts_dir']).glob('*.ttf'))
    if fonts:
        encoded = base64.b64encode(fonts[0].read_bytes()).decode('ascii')
        font_css = f"@font-face {{font-family:ShortsFont;src:url(data:font/ttf;base64,{encoded})}}"

    # Prepare context
    from ..editorial import application_tip
    logo_path = Path(settings['paths']['assets_dir']) / 'branding' / 'unemployer-logo.png'
    cover_amount, cover_period = cover_compensation(script.on_screen.stipend)
    context = {
        'brand_logo': 'data:image/png;base64,' + base64.b64encode(logo_path.read_bytes()).decode('ascii') if logo_path.exists() else '',
        'application_tip': application_tip(script.on_screen.role).removeprefix('Application tip: '),
        'scene_label': {'hook': 'THE OPPORTUNITY', 'facts': 'IS THIS FOR YOU?', 'role': 'INSIDE THE ROLE', 'deadline': 'APPLY SMARTER', 'cta': 'YOUR NEXT STEP'}.get(scene_type,'CAREER GUIDE'),
        **settings.get('enrichment', {}),
        "company": script.on_screen.company,
        "role": script.on_screen.role,
        "location": script.on_screen.location,
        "stipend": script.on_screen.stipend,
        'cover_amount': cover_amount,
        'cover_period': cover_period,
        "eligibility": script.on_screen.eligibility,
        "deadline_badge": script.on_screen.deadline_badge,
        "cta": script.on_screen.cta,
        "layout_variant": settings.get('layout_variant', 0),
        "font_css": font_css,
        "promoted": 'Promoted listing' in script.description.splitlines(),
        "domain": _extract_domain(apply_url) if apply_url else "",
        **theme,
    }

    # Render HTML
    html_content = template.render(**context)

    # Use Playwright to render
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise ImportError("playwright not installed. Run: pip install playwright && playwright install chromium")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1920})
        page.set_content(html_content)
        page.evaluate("document.fonts.ready")
        fits = page.evaluate("""() => {
            const main = document.querySelector('main');
            return !main || (main.scrollHeight <= main.clientHeight && main.scrollWidth <= main.clientWidth);
        }""")
        if not fits:
            browser.close()
            raise ValueError('Scene text exceeds the safe area; shorten listing text before rendering')
        page.screenshot(path=str(output_path))
        browser.close()

    logger.info(f"Rendered scene {scene_type} to {output_path}")
    return output_path


def render_all_scenes(
    script: ScriptDoc,
    output_dir: Path,
    apply_url: str = "",
    settings: Optional[dict] = None,
    theme_index: int = 0
) -> list[Path]:
    """
    Render all scenes for a script.

    Args:
        script: ScriptDoc containing on-screen text
        output_dir: Directory to save rendered images
        apply_url: Application URL for domain extraction
        settings: Settings dict
        theme_index: Starting theme index (for rotation)

    Returns:
        List of paths to rendered scene images in order
    """
    settings = settings or load_shorts_settings()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    theme = _get_theme(settings, theme_index)
    settings = {**settings, 'layout_variant': theme_index % 3}
    scene_paths = []

    for i, scene_type in enumerate(LAYOUT_SEQUENCE):
        output_path = output_dir / f"scene_{i:02d}_{scene_type}.png"
        scene_path = render_scene(scene_type, script, theme, output_path, apply_url, settings)
        scene_paths.append(scene_path)

    # The thumbnail is the actual opening scene, not a different promise/image.
    import shutil
    if scene_paths and scene_paths[0].is_file():
        shutil.copy2(scene_paths[0], output_dir.parent / 'thumbnail.png')

    return scene_paths


def get_scene_specs(
    script: ScriptDoc,
    voiceover_duration: float,
    settings: Optional[dict] = None
) -> list:
    """
    Generate scene specifications with durations based on voiceover timing.

    Args:
        script: ScriptDoc with voiceover lines
        voiceover_duration: Total duration of voiceover in seconds
        settings: Settings dict

    Returns:
        List of scene specs with calculated durations
    """
    settings = settings or load_shorts_settings()
    num_scenes = len(LAYOUT_SEQUENCE)

    weights = [0.10, 0.22, 0.28, 0.25, 0.15] if num_scenes == 5 else [1 / num_scenes] * num_scenes

    specs = []
    for i, scene_type in enumerate(LAYOUT_SEQUENCE):
        specs.append({
            "scene_number": i,
            "layout_name": scene_type,
            "duration_seconds": voiceover_duration * weights[i],
            "theme_index": i % len(settings["theme"]["color_schemes"]),
        })

    return specs
