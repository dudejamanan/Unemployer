from unittest.mock import Mock
from collector.sources.greenhouse import GreenhouseSource


def test_job_location_does_not_inherit_company_hybrid_policy():
    client = Mock()
    client.get_json.return_value = {'jobs': [{'id': 1, 'title': 'Software Intern',
        'location': {'name': 'Onsite in Bangalore'}, 'offices': [{'name': 'Hybrid in Bengaluru, India'}]}]}
    jobs = GreenhouseSource().fetch(client, {'token': 'example', 'company': 'Example'})
    assert jobs[0].location == 'Onsite in Bangalore'


def test_office_location_is_fallback_when_job_location_absent():
    client = Mock()
    client.get_json.return_value = {'jobs': [{'id': 1, 'title': 'Software Intern',
        'offices': [{'name': 'Bengaluru, India'}]}]}
    assert GreenhouseSource().fetch(client, {'token': 'example'})[0].location == 'Bengaluru, India'
