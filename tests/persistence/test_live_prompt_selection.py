"""Opt-in disposable SQL test; metadata and provider response are fabricated."""
import json

import pytest

from rest_api_checker import live_adhoc_request, live_demo
from rest_api_checker.experiment.encoding import digest
from rest_api_checker.persistence.inspection import rows
from .test_experiment import make_stage, FabricatedClient, fabricated

pytestmark = pytest.mark.sqlserver


@pytest.mark.parametrize('prompt_name', ['P1', 'P2', 'P3'])
def test_interactive_prompt_roundtrip_preserves_existing_rows(repo, tmp_path, prompt_name):
    stage = make_stage(repo)
    inventory = live_demo.catalog(repo, adhoc=True)
    case, model = inventory['cases'][0], inventory['models'][0]
    prompt = next(p for p in inventory['prompts'] if p['name'] == prompt_name)
    existing = {table: rows(repo, table) for table in (
        'datasets', 'dataset_cases', 'test_cases', 'responses', 'reference_results',
        'models', 'prompts', 'run_configs', 'experiment_runs')}
    repo.cn.commit()

    def runtime_api(path, data=None):
        if path == '/api/version':
            return {'version': '0.40.0'}
        if path == '/api/tags':
            return {'models': [{'name': model['name'], 'digest': model['digest']}]}
        assert path == '/api/show'
        return {'template': 'FABRICATED native template', 'parameters': '', 'system': ''}

    plan = live_demo.plan(repo, case_id=case['id'], model_ids=[model['id']], repetitions=1,
                         root=tmp_path, adhoc=True, prompt_id=prompt['id'])
    client = FabricatedClient(repo, fabricated())
    result = live_demo.execute(repo, plan, root=tmp_path, spool=tmp_path/'spool',
                              runtime_api=runtime_api, client=client)
    assert result['status'] == 'COMPLETED' and result['experiment_id'] != stage['experiment']
    assert len(client.calls) == 1
    run = repo._row('experiment_runs', result['run_ids'][0])
    assert run['prompt_id'] == prompt['id'] and run['result'] == 'valid'
    request = client.calls[0]
    assert repo.file(run['request_file_id']) == request.body
    assert json.loads(request.body)['messages'][0]['content'].encode() == repo.file(prompt['file_id'])
    inputs, reconstructed = live_adhoc_request.prepare(repo, run['id'])
    assert reconstructed == request
    assert inputs['setup']['prompt_selection'] == dict(prompt_id=prompt['id'], name=prompt_name,
                                                     sha256=digest(repo.file(prompt['file_id'])))
    for table, before in existing.items():
        assert [repo._row(table, row['id']) for row in before] == before
    assert rows(repo, 'evaluation_reports') == []
