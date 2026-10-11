from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Optional

from .settings import load_shorts_settings

logger = logging.getLogger(__name__)


def assemble_video(
    scene_paths: list[Path],
    audio_path: Path,
    output_path: Path,
    word_timestamps: list[dict],
    music_path: Optional[Path] = None,
    settings: Optional[dict] = None
) -> Path:
    """
    Assemble scenes, audio, and optional music into a final video using FFmpeg.

    Args:
        scene_paths: List of scene image paths in order
        audio_path: Path to voiceover audio (MP3)
        output_path: Path for final video output (MP4)
        word_timestamps: List of word timestamps for captions
        music_path: Optional path to background music
        settings: Settings dict

    Returns:
        Path to assembled video
    """
    settings = settings or load_shorts_settings()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    from .captions import write_captions
    cfg = settings["assembly"]
    total_duration = _get_audio_duration(audio_path)
    if not scene_paths:
        raise ValueError("At least one scene is required")
    if not cfg["min_duration"] <= total_duration <= cfg["max_duration"]:
        raise ValueError(f"Voice duration {total_duration:.1f}s outside configured limits")
    output_path = output_path.resolve()
    concat_file = output_path.with_suffix(".concat.txt")
    boundaries = [0.0]
    for i in range(1, len(scene_paths)):
        target = total_duration * i / len(scene_paths)
        candidates = [float(t["start"]) for t in word_timestamps
                      if boundaries[-1] + cfg["min_scene_seconds"] < float(t["start"]) < total_duration]
        boundaries.append(min(candidates, key=lambda t: abs(t-target)) if candidates else target)
    boundaries.append(total_duration)
    def quoted(path):
        return Path(path).resolve().as_posix().replace("'", "'\\''")
    content = "".join(f"file '{quoted(p)}'\nduration {boundaries[i+1]-boundaries[i]:.6f}\n"
                      for i, p in enumerate(scene_paths))
    content += f"file '{quoted(scene_paths[-1])}'\n"
    concat_file.write_text(content, encoding="utf-8")
    vf = (f"scale={cfg['width']}:{cfg['height']}:force_original_aspect_ratio=decrease,"
          f"pad={cfg['width']}:{cfg['height']}:(ow-iw)/2:(oh-ih)/2,fps={cfg['fps']}")
    if word_timestamps:
        captions = output_path.with_suffix(".ass")
        write_captions(word_timestamps, captions, settings)
        vf += f",ass=filename='{captions.name}'"
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
           "-i", str(Path(audio_path).resolve())]
    if music_path:
        gain = max(-22, min(-18, cfg["music_duck_db"]))
        cmd += ["-stream_loop", "-1", "-i", str(Path(music_path).resolve()),
                "-filter_complex", f"[1:a]loudnorm=I=-16:TP=-1.5:LRA=11[voice];[2:a]volume={gain}dB[music];[voice][music]amix=inputs=2:duration=first:normalize=0[a]",
                "-map", "0:v", "-map", "[a]"]
    else:
        cmd += ["-map", "0:v", "-map", "1:a", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11"]
    cmd += ["-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", cfg["preset"],
            "-crf", str(cfg["crf"]), "-c:a", "aac", "-b:a", cfg["audio_bitrate"],
            "-t", str(total_duration), "-movflags", "+faststart", str(output_path)]
    try:
        subprocess.run(cmd, cwd=output_path.parent, stdin=subprocess.DEVNULL, capture_output=True, check=True)
    finally:
        concat_file.unlink(missing_ok=True)
    return output_path


def _get_audio_duration(audio_path: Path) -> float:
    result = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                             "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
                            stdin=subprocess.DEVNULL, capture_output=True, text=True, check=True)
    duration = float(result.stdout.strip())
    if duration <= 0:
        raise ValueError("Audio duration must be positive")
    return duration


assemble_with_captions = assemble_video


def check_ffmpeg() -> bool:
    """Check if FFmpeg is available on PATH."""
    try:
        subprocess.run(["ffmpeg", "-version"], stdin=subprocess.DEVNULL, capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, OSError):
        return False


def check_ffprobe() -> bool:
    """Check if FFprobe is available on PATH."""
    try:
        subprocess.run(["ffprobe", "-version"], stdin=subprocess.DEVNULL, capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, OSError):
        return False
