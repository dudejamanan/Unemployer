# Milestone 3: Visuals - Scene Rendering

## What was built

- `shorts/render/render_scenes.py`: Playwright-based scene rendering
  - `render_scene()`: Render single scene from Jinja2 template to PNG
  - `render_all_scenes()`: Render all 4 scenes (hook, facts, deadline, CTA)
  - `get_scene_specs()`: Generate scene specifications with durations
  - Theme rotation across scenes for variety
  - Safe zones (bottom 22%, right 12%) for YouTube UI overlays
- `shorts/render/templates/`: 4 HTML/CSS scene templates (1080x1920)
  - `hook_scene.html`: Company + role with deadline badge
  - `facts_scene.html`: Location, stipend, eligibility card
  - `deadline_scene.html`: Circular deadline urgency badge
  - `cta_scene.html`: "Apply link in description" with domain preview
- `tests/test_render.py`: 5 unit tests (2 skipped for Playwright integration)
- Updated `shorts/cli.py`: Added `render` command
- Added `jinja2>=3.1.0` to requirements.txt

## Key features

- **1080x1920 resolution**: Vertical aspect ratio for YouTube Shorts
- **Jinja2 templates**: Dynamic HTML generation with color theme substitution
- **Playwright rendering**: Chromium-based screenshot generation
- **Safe zones**: Bottom 22% and right 12% reserved for YouTube UI overlays
- **Theme rotation**: 2 color schemes (blue, purple) rotate across scenes
- **4 scene types**: Hook → Facts → Deadline → CTA
- **Domain extraction**: Shows readable domain (not full URL) on CTA scene
- **Min font size 56px**: Ensures readability on mobile
- **Max 7 words per line**: Prevents overcrowding

## Scene sequence

1. **Hook**: Company name, role, deadline badge (top-right)
2. **Facts**: Card with location, stipend, eligibility
3. **Deadline**: Large circular badge with urgency message
4. **CTA**: "Apply link in description" with domain preview

## Usage

```bash
# Render scenes from a script JSON file
python -m shorts render --script-json script.json --output out/scenes

# Render with specific theme index
python -m shorts render --script-json script.json --theme-index 1
```

## Configuration

Color themes in `config/shorts.yaml`:
```yaml
theme:
  color_schemes:
    - name: blue
      primary: "#1a365d"
      secondary: "#2b6cb0"
      accent: "#4299e1"
      text: "#ffffff"
      background: "#f7fafc"
    - name: purple
      primary: "#44337a"
      secondary: "#6b46c1"
      accent: "#9f7aea"
      text: "#ffffff"
      background: "#faf5ff"
```

## Dependencies

- `playwright>=1.40.0`: Browser automation for rendering
- `jinja2>=3.1.0`: HTML template rendering
- Chromium browser (installed via Playwright)

## External setup required

1. Install Playwright and Chromium:
   ```bash
   pip install playwright
   playwright install chromium
   ```

2. (Optional) Bundle fonts in `assets/fonts/`:
   - Currently uses system fonts (Inter/Noto Sans)
   - For consistency, download and bundle:
     - Inter: https://fonts.google.com/specimen/Inter
     - Noto Sans: https://fonts.google.com/specimen/Noto+Sans

## Tests

```bash
python -m pytest tests/test_render.py -v
```

5 passed, 2 skipped (integration tests require Playwright browser).

## Known limitations

- Font bundling not yet implemented (uses system fonts)
- Templates use Jinja2 syntax which may show CSS lint errors in IDE (false positives)
- Scene duration is evenly distributed (future: align with voiceover line breaks)

## Next steps

M4: Assembly - FFmpeg video assembly from scenes + voice + music
