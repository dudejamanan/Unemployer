# Milestone 1: Script Generation

## What was built

- `shorts/models.py`: Data models for ScriptDoc, SceneSpec, PostRecord
- `shorts/settings.py`: Configuration loader for shorts.yaml and .env
- `shorts/script_gen.py`: LLM-based script generation with Anthropic API + deterministic template fallback
- `shorts/validate_script.py`: Fact-checking validation to ensure script only contains card data
- `shorts/store.py`: PostStore for tracking video generation/upload status in SQLite
- `shorts/cli.py`: CLI with `generate` and `doctor` commands
- `config/shorts.yaml`: Configuration for LLM, voices, theme, upload settings
- `tests/test_script_gen.py`: 9 golden tests covering 3 card types

## Key features

- **ScriptDoc structure**: hook, voiceover_lines, on_screen text, title, description, hashtags
- **Template fallback**: Works without API key, produces valid scripts deterministically
- **Validation**: Ensures no fabricated facts, checks stipend/deadline/company/URL against card
- **Word count**: Target 55-85 words, validation allows 45-110 for flexibility
- **Description format**: Apply URL first, then details, then "Always verify on official site", then hashtags

## Usage

```bash
# Generate script for an opportunity (uses template fallback if no API key)
python -m shorts generate <opportunity_id> --save

# Check dependencies (ffmpeg, playwright, API keys)
python -m shorts doctor
```

## Configuration

Add to `.env`:
```
ANTHROPIC_API_KEY=sk-ant-xxx  # Optional, template fallback if missing
```

## Tests

All 35 tests pass (26 collector + 9 script generation).

```bash
python -m pytest -q
```

## Next steps

M2: Voice generation with edge-tts
