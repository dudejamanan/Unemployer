import re


def is_promoted(card):
    """Mark paid manual listings with an explicit prefix in their description."""
    return bool(re.match(r'\s*(?:promoted|sponsored)\s*:', card.get('description') or '', re.I))


def promoted_script(script):
    return 'Promoted listing' in script.description.splitlines()
