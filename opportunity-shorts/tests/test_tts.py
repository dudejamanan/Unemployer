from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from shorts.tts import (
    _get_cache_key,
    _estimate_word_timestamps,
    get_voice_for_post,
    generate_tts,
    TTSResult,
)
from shorts.models import VoiceoverLine
from shorts.settings import load_shorts_settings


def test_cache_key():
    """Test cache key generation."""
    key1 = _get_cache_key("hello world", "en-IN-AaravNeural")
    key2 = _get_cache_key("hello world", "en-IN-AaravNeural")
    key3 = _get_cache_key("hello world", "en-IN-AarohiNeural")
    key4 = _get_cache_key("different text", "en-IN-AaravNeural")

    assert key1 == key2  # Same text and voice
    assert key1 != key3  # Different voice
    assert key1 != key4  # Different text
    assert len(key1) == 16  # SHA256 truncated to 16 chars


def test_estimate_word_timestamps():
    """Test word timestamp estimation."""
    text = "hello world this is a test"
    duration = 2.5  # seconds
    timestamps = _estimate_word_timestamps(text, duration)

    assert len(timestamps) == 6  # 6 words
    assert timestamps[0]["word"] == "hello"
    assert timestamps[0]["start"] == 0.0
    assert timestamps[-1]["end"] == duration

    # Check that timestamps are monotonically increasing
    for i in range(len(timestamps) - 1):
        assert timestamps[i]["end"] <= timestamps[i + 1]["start"]


def test_estimate_word_timestamps_empty():
    """Test word timestamp estimation with empty text."""
    timestamps = _estimate_word_timestamps("", 1.0)
    assert timestamps == []


def test_voice_alternation():
    """Test voice alternation based on post index."""
    settings = load_shorts_settings()
    settings['voices']['alternate'] = True

    voice0 = get_voice_for_post(0, settings)
    voice1 = get_voice_for_post(1, settings)
    voice2 = get_voice_for_post(2, settings)

    # With alternate=true, should alternate: even=female, odd=male
    assert voice0 != voice1
    assert voice0 == voice2  # Even indices get same voice
    assert voice0 == settings["voices"]["female"]
    assert voice1 == settings["voices"]["male"]


def test_voice_no_alternation():
    """Test voice selection when alternation is disabled."""
    settings = load_shorts_settings()
    settings["voices"]["alternate"] = False

    voice0 = get_voice_for_post(0, settings)
    voice1 = get_voice_for_post(1, settings)

    assert voice0 == voice1
    assert voice0 == settings["voices"]["male"]


@pytest.mark.skip(reason="Requires ffmpeg and edge-tts integration")
@pytest.mark.asyncio
async def test_generate_tts_with_mock():
    """Test TTS generation with mocked edge-tts and ffmpeg."""
    # Skipped: requires actual ffmpeg and edge-tts setup
    pass


@pytest.mark.skip(reason="Requires ffmpeg for duration check")
@pytest.mark.asyncio
async def test_generate_tts_cache_hit():
    """Test TTS generation uses cache when available."""
    # Skipped: requires actual ffmpeg setup
    pass


def test_tts_result_dataclass():
    """Test TTSResult dataclass."""
    result = TTSResult(
        audio_path="/path/to/audio.mp3",
        duration_seconds=10.5,
        word_timestamps=[
            {"word": "hello", "start": 0.0, "end": 0.5},
            {"word": "world", "start": 0.5, "end": 1.0},
        ]
    )

    assert result.audio_path == "/path/to/audio.mp3"
    assert result.duration_seconds == 10.5
    assert len(result.word_timestamps) == 2
