from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from shorts.assemble import (
    _get_audio_duration,
    check_ffmpeg,
    check_ffprobe,
)


def test_check_ffmpeg():
    """Test FFmpeg availability check."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock()
        assert check_ffmpeg() is True

        mock_run.side_effect = FileNotFoundError()
        assert check_ffmpeg() is False


def test_check_ffprobe():
    """Test FFprobe availability check."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock()
        assert check_ffprobe() is True

        mock_run.side_effect = FileNotFoundError()
        assert check_ffprobe() is False


def test_get_audio_duration():
    """Test audio duration extraction."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="25.5")
        duration = _get_audio_duration(Path("test.mp3"))
        assert duration == 25.5


def test_get_audio_duration_error():
    """Test audio duration extraction with error."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = Exception("ffprobe failed")
        with pytest.raises(Exception, match='ffprobe failed'):
            _get_audio_duration(Path("test.mp3"))


@pytest.mark.skip(reason="Requires FFmpeg and actual audio file")
def test_assemble_video_integration():
    """Integration test for video assembly (requires FFmpeg)."""
    # This test would require actual FFmpeg installation
    # and is skipped by default
    pass


@pytest.mark.skip(reason="Requires FFmpeg and actual assets")
def test_assemble_with_captions_integration():
    """Integration test for assembly with captions (requires FFmpeg)."""
    # This test would require actual FFmpeg installation
    # and is skipped by default
    pass


@pytest.mark.skipif(not check_ffmpeg() or not check_ffprobe(), reason='Requires FFmpeg and FFprobe')
def test_real_captioned_assembly_with_music(tmp_path):
    import json
    import subprocess
    from shorts.assemble import assemble_with_captions
    from shorts.settings import load_shorts_settings
    scene = tmp_path / 'scene.png'
    audio = tmp_path / 'voice.wav'
    music = tmp_path / 'music.wav'
    def run(args):
        return subprocess.run(args, stdin=subprocess.DEVNULL, capture_output=True, text=True, check=True)
    run(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'color=c=navy:s=320x560', '-frames:v', '1', str(scene)])
    run(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=5', str(audio)])
    run(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'sine=frequency=220:duration=1', str(music)])
    settings = load_shorts_settings()
    settings['assembly'].update(width=320, height=560, min_duration=1, preset='ultrafast')
    timestamps = [{'word': 'Official', 'start': 0, 'end': 2}, {'word': 'listing', 'start': 2, 'end': 4}]
    for background in (None, music):
        output = tmp_path / ('music.mp4' if background else 'plain.mp4')
        assemble_with_captions([scene, scene], audio, output, timestamps, background, settings)
        result = run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(output)])
        probe = json.loads(result.stdout)
        assert {stream['codec_name'] for stream in probe['streams']} == {'h264', 'aac'}
        assert probe['streams'][0]['width'] == 320
        assert 4.9 <= float(probe['format']['duration']) <= 5.2
        import re
        caption_text = re.sub(r'\{[^}]*\}', '', output.with_suffix('.ass').read_text())
        assert 'OFFICIAL LISTING' in caption_text
