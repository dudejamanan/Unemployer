from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from shorts.render.render_scenes import (
    _extract_domain,
    _get_theme,
    get_scene_specs,
    LAYOUT_SEQUENCE,
    SCENE_TEMPLATES,
)
from shorts.models import ScriptDoc, OnScreenText
from shorts.settings import load_shorts_settings


def test_extract_domain():
    """Test domain extraction from URLs."""
    assert _extract_domain("https://careers.google.com/jobs/123") == "careers.google.com"
    assert _extract_domain("https://www.flipkart.com/careers") == "flipkart.com"
    assert _extract_domain("http://example.org/hack") == "example.org"
    # Invalid URLs return empty string or the input
    assert _extract_domain("invalid-url") in ["", "invalid-url"]


def test_layout_sequence():
    """Test that layout sequence is defined."""
    assert LAYOUT_SEQUENCE == ["hook", "facts", "role", "deadline", "cta"]
    assert len(LAYOUT_SEQUENCE) == 5


def test_cover_preserves_compensation_qualifiers():
    from shorts.render.render_scenes import cover_compensation
    assert cover_compensation('INR 45000 / monthly') == ('₹45,000', 'per month')
    assert cover_compensation('Up to INR 5000-20000/month') == ('Up to ₹5,000–20,000', 'per month')
    assert cover_compensation('USD 5000/year') == ('USD 5000/year', '')


def test_scene_templates():
    """Test that all scene templates are defined."""
    for scene_type in LAYOUT_SEQUENCE:
        assert scene_type in SCENE_TEMPLATES
        assert SCENE_TEMPLATES[scene_type].endswith(".html")


def test_get_theme_rotation():
    """Test theme rotation."""
    settings = load_shorts_settings()
    themes = settings["theme"]["color_schemes"]

    theme0 = _get_theme(settings, 0)
    theme1 = _get_theme(settings, 1)
    theme2 = _get_theme(settings, 2)

    assert theme0 == themes[0]
    assert theme1 == themes[1]
    assert theme2 == themes[0]  # Should wrap around


def test_get_scene_specs():
    """Test scene specification generation."""
    script = ScriptDoc(
        hook="Test hook",
        voiceover_lines=[],
        on_screen=OnScreenText(
            role="Test Role",
            company="Test Company",
            location="Bengaluru",
            stipend="Rs 25,000",
            eligibility="2027 batch",
            deadline_badge="Apply soon",
            cta="Apply link in description",
        ),
        title="Test",
        description="Test",
        hashtags=[],
    )

    specs = get_scene_specs(script, 25.0)

    assert len(specs) == 5
    assert specs[0]["layout_name"] == "hook"
    assert specs[1]["layout_name"] == "facts"
    assert specs[2]["layout_name"] == "role"
    assert specs[3]["layout_name"] == "deadline"
    assert specs[4]["layout_name"] == "cta"

    # Check duration distribution
    total_duration = sum(s["duration_seconds"] for s in specs)
    assert abs(total_duration - 25.0) < 0.1

    # Check theme rotation
    assert specs[0]["theme_index"] == 0
    assert specs[1]["theme_index"] == 1


@pytest.mark.skip(reason="Requires Playwright browser installation")
def test_render_scene_integration():
    """Integration test for scene rendering (requires Playwright)."""
    # This test would require actual Playwright installation
    # and is skipped by default
    pass


@pytest.mark.skip(reason="Requires Playwright browser installation")
def test_render_all_scenes_integration():
    """Integration test for rendering all scenes (requires Playwright)."""
    # This test would require actual Playwright installation
    # and is skipped by default
    pass
