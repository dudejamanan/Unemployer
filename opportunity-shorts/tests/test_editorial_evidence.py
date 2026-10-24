from shorts.editorial import evidence_panel


def test_evidence_is_source_text_not_generated_advice():
    card = {'description': '<p>Responsibilities</p><p>Build REST APIs with Python.</p>'}
    panel = evidence_panel(card, '2026-10-20T10:00:00Z')
    assert panel['source_excerpt'] == 'Responsibilities Build REST APIs with Python.'
    assert panel['source_checked'] == '2026-10-20'
    assert panel['role_explainer'].startswith('An API')
    assert 'verified' not in panel['source_label'].lower()


def test_unknown_details_remain_unknown():
    panel = evidence_panel({'description': ''})
    assert not panel['source_excerpt']
    assert not panel['role_explainer']
    assert not panel['source_checked']


def test_excerpt_is_contiguous_and_bounded():
    text = 'Build ' + 'useful applications ' * 40
    excerpt = evidence_panel({'description': text})['source_excerpt']
    assert len(excerpt) <= 191
    assert text.startswith(excerpt.removesuffix('…'))
