"""Render an unpublished editorial-format preview from a collected opportunity."""
import asyncio
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shorts.pipeline import Pipeline
from shorts.script_gen import generate_script
from shorts.editorial import evidence_panel, VERSION
from shorts.render.render_scenes import render_all_scenes
from shorts.tts import generate_tts
from shorts.assemble import assemble_with_captions


def main():
    p = Pipeline()
    try:
        card = p.card(sys.argv[1])
        folder = Path(p.settings['paths']['output_dir']) / ('enriched-preview-' + card['id'])
        folder.mkdir(parents=True, exist_ok=True)
        settings = {**p.settings, 'script': {**p.settings['script'], 'max_words': 65}}
        script_path = folder / 'script.json'
        if '--reuse-script' in sys.argv and script_path.exists():
            from shorts.models import ScriptDoc
            from shorts.editorial import tighten_narration
            script = tighten_narration(ScriptDoc.from_dict(json.loads(script_path.read_text(encoding='utf-8'))), card, 65)
        else:
            script = generate_script(card, settings)
        from shorts.validate_script import validate_script
        valid, errors = validate_script(script, card)
        if not valid:
            raise ValueError('; '.join(errors))
        source = p.db.get(card['id'])
        evidence = evidence_panel(card, source['last_seen_at'])
        settings['enrichment'] = evidence
        (folder / 'script.json').write_text(json.dumps(script.to_dict(), ensure_ascii=False, indent=2), encoding='utf-8')
        (folder / 'source-evidence.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
        print('Narration words:', len(' '.join(l.text for l in script.voiceover_lines).split()), flush=True)
        audio = asyncio.run(generate_tts(' '.join(l.text for l in script.voiceover_lines), settings['voices']['male'], settings))
        scenes = render_all_scenes(script, folder / 'scenes', card['apply_url'], settings)
        video = assemble_with_captions(scenes, Path(audio.audio_path), folder / 'video.mp4', audio.word_timestamps, settings=settings)
        (folder / 'preview.json').write_text(json.dumps({'editorial': VERSION, 'source_url': card['apply_url'], 'duration': audio.duration_seconds, 'published': False},indent=2), encoding='utf-8')
        print(json.dumps({'video': str(video), 'duration': audio.duration_seconds}), flush=True)
    finally:
        p.close()


if __name__ == '__main__':
    main()
