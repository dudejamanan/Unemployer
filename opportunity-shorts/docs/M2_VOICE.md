# Milestone 2: Voice Generation

## What was built

- `shorts/tts.py`: Text-to-speech generation using edge-tts
  - `generate_tts()`: Async function to generate audio from text
  - `generate_voiceover()`: Generate and concatenate multiple voiceover lines
  - `get_voice_for_post()`: Alternate between male/female voices for variety
  - Caching by hash of text+voice combination
  - Loudness normalization with ffmpeg loudnorm filter
  - Word timestamp estimation for caption synchronization
- `tests/test_tts.py`: 6 unit tests (2 skipped for integration tests requiring ffmpeg)
- Updated `shorts/cli.py`: Added `tts` command for testing TTS generation
- Updated `config/shorts.yaml`: Configured Indian-English voices (en-IN-AaravNeural, en-IN-AarohiNeural)

## Key features

- **edge-tts integration**: Uses Microsoft Edge's free TTS API
- **Indian-English voices**: Default voices are en-IN-AaravNeural (male) and en-IN-AarohiNeural (female)
- **Voice alternation**: Automatically alternates between voices for variety across posts
- **Caching**: Audio cached by SHA256 hash of text+voice to avoid redundant generation
- **Loudness normalization**: Uses ffmpeg loudnorm filter (I=-16, TP=-1.5, LRA=11) for consistent audio levels
- **Word timestamps**: Estimates word boundaries for caption synchronization (fallback when edge-tts doesn't provide precise boundaries)
- **Duration detection**: Uses ffprobe to get accurate audio duration

## Usage

```bash
# Generate TTS for a text string (uses cache by default)
python -m shorts tts "Hello world, this is a test"

# Generate with specific voice
python -m shorts tts "Hello world" --voice en-IN-AarohiNeural

# Bypass cache
python -m shorts tts "Hello world" --no-cache

# List available voices
edge-tts --list-voices | grep "en-IN"
```

## Configuration

Voices configured in `config/shorts.yaml`:
```yaml
voices:
  male: en-IN-AaravNeural
  female: en-IN-AarohiNeural
  alternate: true
```

## Dependencies

- `edge-tts>=6.1.0`: TTS generation
- `ffmpeg`: Required for loudness normalization and duration detection
- `pytest-asyncio`: For async test support

## External setup required

1. Install FFmpeg and add to PATH:
   - Windows: Download from https://ffmpeg.org/download.html
   - Mac: `brew install ffmpeg`
   - Linux: `sudo apt install ffmpeg`

2. Install edge-tts (already in requirements.txt):
   ```bash
   pip install edge-tts
   ```

## Tests

```bash
python -m pytest tests/test_tts.py -v
```

6 passed, 2 skipped (integration tests require ffmpeg setup).

## Next steps

M3: Visuals - HTML/CSS scene templates rendered with Playwright
