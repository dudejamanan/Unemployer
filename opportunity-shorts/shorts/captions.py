from pathlib import Path


def _time(seconds):
    ticks = round(max(0, seconds) * 100)
    hours, rest = divmod(ticks, 360000)
    minutes, rest = divmod(rest, 6000)
    seconds, fraction = divmod(rest, 100)
    return f'{hours}:{minutes:02}:{seconds:02}.{fraction:02}'


def write_captions(timestamps, path: Path, settings):
    cfg = settings['captions']
    header = f'''[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{cfg['font']},{cfg['font_size']},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,{cfg['outline']},0,2,{cfg['margin_side']},{cfg['margin_side']},{cfg['margin_bottom']},1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    groups, group = [], []
    for item in timestamps:
        if group and (len(group) >= cfg['max_words'] or item['start']-group[-1]['end'] > cfg['max_gap_seconds']):
            groups.append(group)
            group = []
        group.append(item)
    if group:
        groups.append(group)
    lines = []
    for group in groups:
        text = ' '.join(str(t['word']) for t in group).replace('\\', '').replace('{', '').replace('}', '').replace('\n', ' ')
        if cfg['uppercase']:
            text = text.upper()
        lines.append(f"Dialogue: 0,{_time(group[0]['start'])},{_time(group[-1]['end'])},Default,,0,0,0,,{text}\n")
    path.write_text(header + ''.join(lines), encoding='utf-8')
    return path
