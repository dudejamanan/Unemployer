from PIL import Image
import pytest
from shorts.linkedin_card import facts,render_card


def test_card_preserves_pay_qualifiers_and_does_not_invent_duration():
    data=facts({'title':'AI intern','stipend_text':'Up to INR 30000 / monthly','opp_type':'internship'})
    assert data['pay']=='Up to ₹30,000 / month'
    assert data['location']=='Location not disclosed'
    assert 'duration' not in data


def test_card_preserves_unknown_compensation_period():
    assert facts({'title':'Intern','stipend_text':'INR 30000'})['pay']=='INR 30000'


def test_card_handles_long_source_title(tmp_path):
    file=render_card({'title':'Intern - Artificial Intelligence and Software Engineering, Infrastructure and Developer Tools','company':'Example employer','opp_type':'internship'},tmp_path/'card.png')
    with Image.open(file) as image:assert image.size==(1200,628) and image.format=='PNG'


def test_card_requires_real_role_title(tmp_path):
    with pytest.raises(ValueError):render_card({},tmp_path/'card.png')
