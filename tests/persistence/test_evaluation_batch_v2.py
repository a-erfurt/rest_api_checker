"""Opt-in disposable SQL round trip through the unchanged real attempt executor."""
from dataclasses import asdict
import json

import pytest

from rest_api_checker import evaluation_batch_v2 as v2
from rest_api_checker.experiment import parser, renderer, request, request_v2
from rest_api_checker.experiment.encoding import digest, encode
from rest_api_checker.persistence.importer import import_development, import_prompts
from rest_api_checker.persistence.inspection import bindings, rows
from rest_api_checker.persistence.repository import D07
from rest_api_checker.sensitivity_freeze import snapshot
from .conftest import ROOT, RESEARCH
from .test_experiment import FabricatedClient, fabricated

pytestmark = pytest.mark.sqlserver


def materialize_fixture(repo, root):
    """Test-only materialization; never provided as a scientific release command."""
    imported = import_development(repo, ROOT/'artifacts/development_dataset_v1',
                                  ROOT/'docs/development_dataset_v1_release.json', RESEARCH)
    prompt_id = import_prompts(repo, RESEARCH)['prompt_ids']['P2']
    original = repo._row('dataset_cases', imported['membership_ids'][0])
    dataset = repo.dataset('FABRICATED v2 adapter verification', 'test-only', 'evaluation')
    member = repo.membership(dataset, original['case_id'], original['reference_id'], 'SIM-ONLY', 1)
    case = repo._row('test_cases', original['case_id'])
    operation = repo._row('api_operations', case['operation_id'])
    contract = repo._row('api_contracts', operation['contract_id'])
    response = repo._row('responses', case['response_id'])
    rendered = renderer.render(renderer.Evidence(repo.file(contract['file_id']), operation['http_method'],
        operation['path_template'], response['status_code'], response['content_type'], repo.file(response['body_file_id'])),
        contract_identity=f'files:{contract["file_id"]}', body_identity=f'files:{response["body_file_id"]}')
    prompt = repo.file(repo._row('prompts', prompt_id)['file_id'])
    schedule, identities, inventory, proofs = [], [], [], {}
    native = root/v2.runtime_evidence.DIRECTORY
    native.mkdir(parents=True)
    for n, name in enumerate(request.MODELS, 1):
        model = repo.model(name=name, family='FABRICATED', parameters_b=None, quantization='Q4_K_M',
            context_length=request.OPTIONS['num_ctx'], digest=str(n)*64, architecture='FABRICATED')
        config = repo.configuration(think=False if n == 1 else None, **D07)
        (native/f'{n}.json').write_bytes(encode(dict(template='FABRICATED')))
        identities.append(dict(name=name, digest=str(n)*64, show=f'{n}.json', template_sha256=digest(b'FABRICATED')))
        for repetition, seed in request.SEEDS.items():
            order = len(schedule)+1
            schedule.append(dict(dataset_case_id=member, model_id=model, prompt_id=prompt_id,
                run_config_id=config, repetition=repetition, seed=seed, run_order=order))
            req = request_v2.build_request_v2(rendered, interface=request_v2.OutputInterfaceV2('format_json'),
                prompt=prompt, model=name, model_digest=str(n)*64, repetition=repetition)
            inventory.append(dict(run_order=order, sha256=digest(req.body), request_identity_sha256=req.metadata['request_identity_sha256']))
            proofs[str(order)] = asdict(request.ContextProof(digest(req.body), str(n)*64, digest(b'FABRICATED'), 'f'*64, 10000))
    setup = dict(format='main-evaluation-setup-v2', dataset_id=dataset, schedule=schedule, schedule_seed=17,
        files=[dict(file_id=case['source_file_id'], sha256=digest(repo.file(case['source_file_id'])))],
        parser_sha256=parser.artifact_hash(), renderer_sha256=renderer.artifact_hash(),
        request_builder_sha256=request_v2.artifact_hash(), output_interface={'mode':'format_json'},
        models=identities, runtime={'ollama':{'version':'FABRICATED'}}, context_proofs=proofs,
        request_inventory=inventory, gate_b_complete=True, plan_authorized=True, execution_authorized=False,
        bindings=bindings(repo, dataset, schedule))
    with repo.transaction():
        setup_id = repo.archive('FABRICATED-v2-setup.json', encode(setup))
        experiment = repo._insert('experiments', name='FABRICATED v2 transport test', kind='evaluation', dataset_id=dataset,
            setup_file_id=setup_id, schedule_seed=17, started_at=None, finished_at=None, notes='FABRICATED; disposable SQL only')
        for slot in schedule:
            repo._insert('experiment_runs', experiment_id=experiment, dataset_id=dataset, **slot)
    from rest_api_checker.main_v2_authorization import execution_template, authorize_execution
    database = repo.cn.execute('SELECT DB_NAME()').fetchval()
    approval = execution_template(repo, dataset, experiment, database=database, root=root, live_check=lambda *a: True)
    approval.update(decision='AUTHORIZE_MAIN_V2_EXECUTION', author='FABRICATED TEST ONLY', accepted_at='2026-10-03T12:00:00+02:00')
    path = root/'FABRICATED-authorization.json'
    path.write_bytes(encode(approval))
    authorize_execution(repo, dataset, experiment, path, database=database, root=root, live_check=lambda *a: True)
    return dataset, experiment


@pytest.mark.parametrize('technical', [False, True])
def test_sql_v2_preflight_executor_spool_and_safe_continuation(repo, db, tmp_path, technical):
    dataset, experiment = materialize_fixture(repo, tmp_path)
    before = snapshot(repo)
    plan = v2.preflight(repo, dataset, experiment, database=db, root=tmp_path, live_check=lambda *a: True)
    assert snapshot(repo) == before
    client = FabricatedClient(repo, fabricated('```invalid```', technical=technical))
    result = v2.execute(repo, plan, root=tmp_path, spool=tmp_path/'spool', resume=False,
                        notify=lambda e: None, client=client, live_check=lambda *a: True)
    assert not rows(repo, 'predictions')
    if technical:
        assert len(client.calls) == 1 and result['exit_code'] == 3
        assert result['counts_now']['parser_failure'] == 0
        state = v2.inspect_plan(repo, dataset, experiment, database=db)
        assert state.summary['problematic'] == 1
        with pytest.raises(ValueError, match='RECONCILIATION'):
            v2.require_continuation(state, True)
    else:
        assert len(client.calls) == 9 and result['exit_code'] == 0
        assert result['counts_now']['parser_failure'] == 9
        frozen = snapshot(repo)
        resumed = v2.preflight(repo, dataset, experiment, database=db, root=tmp_path, live_check=lambda *a: True)
        result = v2.execute(repo, resumed, root=tmp_path, spool=tmp_path/'spool', resume=True,
                            notify=lambda e: None, client=client, live_check=lambda *a: True)
        assert result['executed_now'] == 0 and len(client.calls) == 9
        assert snapshot(repo) == frozen
    assert len(list((tmp_path/'spool').glob('*.json'))) == len(client.calls)
    for req in client.calls:
        request_v2.validate_request_v2(req)
        assert json.loads(req.body)['format'] == 'json'
