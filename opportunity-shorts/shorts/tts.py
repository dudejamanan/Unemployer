from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .models import VoiceoverLine
from .settings import load_shorts_settings

logger = logging.getLogger(__name__)


@dataclass
class TTSResult:
    """Result of text-to-speech generation."""
    audio_path: str  # Path to MP3 file
    duration_seconds: float
    word_timestamps: list[dict]  # [{"word": "hello", "start": 0.0, "end": 0.5}, ...]


def _get_cache_key(text: str, voice: str) -> str:
    """Generate cache key for text+voice combination."""
    raw = f"{text}|{voice}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _get_cache_dir(settings: dict) -> Path:
    """Get cache directory for TTS audio."""
    cache_dir = Path(settings["paths"]["output_dir"]) / "cache" / "tts"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


async def _generate_with_edge_tts(text: str, voice: str, output_path: Path) -> list[dict]:
    import edge_tts
    communicate = edge_tts.Communicate(text, voice, boundary="WordBoundary")
    timestamps = []
    with output_path.open("wb") as audio:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / 10_000_000
                timestamps.append({"word": chunk["text"], "start": start,
                                   "end": start + chunk["duration"] / 10_000_000})
    if not output_path.stat().st_size:
        raise RuntimeError("TTS returned empty audio")
    return timestamps


def _normalize_loudness(input_path: Path, output_path: Path) -> None:
    """Normalize audio loudness using ffmpeg loudnorm filter."""
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(input_path),
                "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                "-b:a", "128k",
                str(output_path)
            ],
            stdin=subprocess.DEVNULL, capture_output=True, check=True
        )
    except subprocess.CalledProcessError as e:
        logger.warning(f"Loudness normalization failed: {e}")
        # Fallback: just copy the file
        import shutil
        shutil.copy(input_path, output_path)


def _estimate_word_timestamps(text: str, duration: float) -> list[dict]:
    """
    Estimate word timestamps based on duration and word count.
    This is a fallback when edge-tts doesn't provide precise word boundaries.
    """
    words = text.split()
    if not words:
        return []

    # Distribute time evenly among words (rough approximation)
    time_per_word = duration / len(words)
    timestamps = []
    current_time = 0.0

    for word in words:
        timestamps.append({
            "word": word,
            "start": current_time,
            "end": current_time + time_per_word
        })
        current_time += time_per_word

    return timestamps


async def generate_tts(
    text: str,
    voice: Optional[str] = None,
    settings: Optional[dict] = None,
    use_cache: bool = True
) -> TTSResult:
    """
    Generate text-to-speech audio with word timestamps.

    Args:
        text: Text to convert to speech
        voice: Edge-tts voice name (e.g., "en-IN-NeerjaNeural")
        settings: Settings dict (loaded from config if None)
        use_cache: Whether to use cached audio if available

    Returns:
        TTSResult with audio path, duration, and word timestamps
    """
    settings = settings or load_shorts_settings()
    voice = voice or settings["voices"]["male"]
    if not text.strip():
        raise ValueError("Narration text cannot be empty")
    from .assemble import _get_audio_duration
    cache_key = _get_cache_key(text, voice)
    cache_dir = _get_cache_dir(settings)
    cached_path = cache_dir / f"{cache_key}.mp3"
    metadata = cache_dir / f"{cache_key}.json"
    if use_cache and cached_path.exists() and metadata.exists():
        duration = _get_audio_duration(cached_path)
        return TTSResult(str(cached_path), duration, json.loads(metadata.read_text(encoding="utf-8")))
    temp_path = cache_dir / f"{cache_key}_temp.mp3"
    try:
        timestamps = await asyncio.wait_for(_generate_with_edge_tts(text, voice, temp_path), timeout=90)
        _normalize_loudness(temp_path, cached_path)
        duration = _get_audio_duration(cached_path)
        timestamps = timestamps or _estimate_word_timestamps(text, duration)
        metadata.write_text(json.dumps(timestamps, ensure_ascii=False), encoding="utf-8")
        return TTSResult(str(cached_path), duration, timestamps)
    finally:
        temp_path.unlink(missing_ok=True)


def get_voice_for_post(post_index: int, settings: Optional[dict] = None) -> str:
    """
    Get voice name for a post, alternating between male/female if configured.
    """
    settings = settings or load_shorts_settings()
    if settings["voices"]["alternate"]:
        return settings["voices"]["female"] if post_index % 2 == 0 else settings["voices"]["male"]
    return settings["voices"]["male"]


async def generate_voiceover(
    lines: list[VoiceoverLine],
    voice: Optional[str] = None,
    settings: Optional[dict] = None
) -> tuple[str, float, list[dict]]:
    """
    Generate voiceover for multiple lines and concatenate them.

    Args:
        lines: List of VoiceoverLine objects
        voice: Edge-tts voice name
        settings: Settings dict

    Returns:
        (audio_path, total_duration, all_word_timestamps)
    """
    if not lines:
        raise ValueError("Narration lines cannot be empty")
    result = await generate_tts(" ".join(line.text for line in lines), voice, settings)
    # Assign line boundaries from the continuous narration's word timings.
    offset = 0
    for line in lines:
        count = len(line.text.split())
        group = result.word_timestamps[offset:offset+count]
        if group:
            line.start_seconds, line.end_seconds = group[0]["start"], group[-1]["end"]
        offset += count
    return result.audio_path, result.duration_seconds, result.word_timestamps
