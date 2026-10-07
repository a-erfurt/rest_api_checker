"""Opt-in disposable SQL round trips with fabricated native/model receipts only."""
from copy import deepcopy
import json

import pytest

from rest_api_checker import live_demo as demo
from rest_api_checker.experiment.encoding import encode
from rest_api_checker.persistence.inspection import rows
from .test_experiment import make_stage, FabricatedClient, fabricated, VALID

pytestmark = pytest.mark.sqlserver


def fake_native(url, payload):
    if url.endswith('/api/chat'):
        assert payload['_debug_render_only'] is True and payload['truncate'] is False
        return encode({'_debug_info': {'rendered_template':'\n'.join(m['content'] for m in payload['messages'])}})
    assert payload['add_special'] is True and payload['parse_special'] is True
    return encode({'tokens':[1,2,3]})


@pytest.mark.parametrize('content,expected', [(VALID, 'valid'), ('```json\n{}\n```', 'parser_failure')])
def test_live_demo_new_experiment_retains_original_data(repo, tmp_path, monkeypatch, content, expected):
    stage = make_stage(repo)
    inventory = demo.catalog(repo)
    selected = inventory['cases'][0]
    model = inventory['models'][0]
    binding = dict(runtime={'runtime_identity':'evaluation_v2_FABRICATED_SQL'}, models=[
        dict(name=model['name'], digest=model['digest'], template_sha256='b'*64)])
    monkeypatch.setattr(demo, 'load_runtime', lambda *a: (deepcopy(binding), {'runtime-binding.json':encode(binding)}))
    original_runs = rows(repo, 'experiment_runs', experiment_id=stage['experiment'])
    original_sources = {table:rows(repo,table) for table in ('datasets','dataset_cases','test_cases','responses',
        'reference_results','models','prompts','run_configs')}
    old_experiments = rows(repo, 'experiments')
    repo.cn.commit()
    plan = demo.plan(repo, case_id=selected['id'], model_ids=[model['id']], repetitions=1,
                     runtime_path=tmp_path/'fabricated-binding.json', root=tmp_path)
    assert rows(repo,'experiments') == old_experiments
    client = FabricatedClient(repo, fabricated(content))
    result = demo.execute(repo, plan, root=tmp_path, spool=tmp_path/'spool', client=client,
        live_check=lambda *a: True, transport=fake_native,
        runner=lambda i: ('FABRICATED native runner','http://127.0.0.1:19876/tokenize'))
    assert result['status'] == 'COMPLETED' and result['exit_code'] == 0
    assert result['experiment_id'] != stage['experiment'] and result['experiment_id'] != 10003
    assert len(client.calls) == len(result['run_ids']) == 1
    run = repo._row('experiment_runs', result['run_ids'][0])
    assert run['result'] == expected and run['dataset_id'] != 3
    assert len(rows(repo,'run_attempts',run_id=run['id'])) == 1
    assert len(rows(repo,'predictions',run_id=run['id'])) == (expected=='valid')
    assert rows(repo, 'experiment_runs', experiment_id=stage['experiment']) == original_runs
    assert {table:rows(repo,table) for table in original_sources} == original_sources
    assert rows(repo,'evaluation_reports') == []
    stored = repo._row('experiments', result['experiment_id'])
    assert stored['name'].startswith('LIVE-DEMO ')
    setup = json.loads(repo.file(stored['setup_file_id']))
    assert setup['format'] == demo.FORMAT and setup['scientific_evaluation'] is False
    assert setup['context_proofs']['1']['input_tokens'] == 3
    detail = result['results'][0]
    assert detail['attempts'][0]['response_file_id'] is not None
    assert (detail['prediction'] is not None) == (expected=='valid')
