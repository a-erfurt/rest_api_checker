"""Opt-in disposable SQL + read-only Web UI; model/runtime receipts are fabricated."""
from contextlib import closing, contextmanager
from copy import deepcopy
import json

from fastapi.testclient import TestClient
import pytest

from rest_api_checker import live_demo as demo
from rest_api_checker.persistence.database import connect
from rest_api_checker.persistence.inspection import rows
from rest_api_checker.web.app import create_app
from rest_api_checker.web.queries import WebQueries
from .test_experiment import make_stage, FabricatedClient, fabricated, VALID

pytestmark = pytest.mark.sqlserver
CURRENT_DIGEST = 'd' * 64
SHOW = dict(template='FABRICATED current Gemma template', parameters='FABRICATED', system='',
    details=dict(family='gemma3', parameter_size='27B', quantization_level='Q4_K_M'),
    model_info={'general.architecture': 'gemma3', 'general.parameter_count': 27000000000,
                'gemma3.context_length': 32768})


def test_current_digest_roundtrip_and_db_backed_browse_web_keep_historical_rows(repo, tmp_path, settings, db):
    make_stage(repo)
    inventory = demo.catalog(repo, adhoc=True)
    case = inventory['cases'][0]
    historical_model = next(model for model in inventory['models'] if model['name'] == 'gemma3:27b')
    before = {table: rows(repo, table) for table in ('models', 'datasets', 'dataset_cases', 'test_cases',
        'responses', 'reference_results', 'experiments', 'experiment_runs', 'run_attempts', 'predictions')}
    before_files = {row['id']: repo.file(row['id']) for row in rows(repo, 'files')}
    def api(path, data=None):
        if path == '/api/version':
            return {'version': '0.40.0'}
        if path == '/api/tags':
            return {'models': [dict(name='gemma3:27b', digest=CURRENT_DIGEST)]}
        assert path == '/api/show' and data == {'model': 'gemma3:27b'}
        return deepcopy(SHOW)
    plan = demo.plan(repo, case_id=case['id'], model_ids=[historical_model['id']],
                     repetitions=1, root=tmp_path, adhoc=True)
    client = FabricatedClient(repo, fabricated(VALID))
    result = demo.execute(repo, plan, root=tmp_path, spool=tmp_path/'spool', runtime_api=api, client=client)
    assert result['status'] == 'COMPLETED', result
    assert len(client.calls) == 1 and result['experiment_id'] != 10003
    run = repo._row('experiment_runs', result['run_ids'][0])
    assert run['result'] == 'valid' and run['dataset_id'] != 3
    model = repo._row('models', run['model_id'])
    assert model['id'] != historical_model['id'] and model['digest'] == CURRENT_DIGEST
    assert json.loads(repo.file(model['metadata_file_id'])) == SHOW
    experiment = repo._row('experiments', result['experiment_id'])
    setup = json.loads(repo.file(experiment['setup_file_id']))
    assert setup['runtime']['ollama']['version'] == '0.40.0'
    assert setup['models'][0]['digest'] == CURRENT_DIGEST
    for table, original in before.items():
        assert [repo._row(table, row['id']) for row in original] == original
    assert {file_id: repo.file(file_id) for file_id in before_files} == before_files
    assert len(rows(repo, 'predictions', run_id=run['id'])) == 1
    assert len(rows(repo, 'run_attempts', run_id=run['id'])) == 1
    repo.cn.commit()

    @contextmanager
    def queries():
        with closing(connect(settings, db)) as cn:
            try:
                yield WebQueries(cn)
            finally:
                cn.rollback()
    with queries() as query:
        assert result['experiment_id'] in {row['id'] for row in query.experiments()}
        assert run['id'] in {row['id'] for row in query.runs(experiment_id=result['experiment_id'])['items']}
        detail = query.run_detail(run['id'])
        assert detail['prediction'] is not None and detail['reference'] is not None
        assert detail['run']['model'] == 'gemma3:27b'
    with TestClient(create_app(query_factory=queries)) as browser:
        listing = browser.get('/runs', params={'experiment': result['experiment_id']})
        detail_page = browser.get(f'/runs/{run["id"]}')
        assert listing.status_code == detail_page.status_code == 200
        assert f'/runs/{run["id"]}' in listing.text
        assert 'Gemma' in detail_page.text
        assert 'FABRICATED test answer' in detail_page.text
