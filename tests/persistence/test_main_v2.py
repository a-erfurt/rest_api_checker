"""Real SQL roundtrips in fixture-owned disposable databases; no model calls."""
import json
import urllib.request

import pytest

from rest_api_checker import evaluation_batch_v2 as batch, main_v2 as main
from rest_api_checker.experiment import request
from rest_api_checker.persistence.inspection import rows
from rest_api_checker.sensitivity_freeze import snapshot
from .main_v2_helpers import prepared_context, authorize

pytestmark = pytest.mark.sqlserver


@pytest.mark.parametrize('n', [1, 3])
def test_materializer_roundtrip_pristine_and_real_runner_dry_run(repo, db, tmp_path, monkeypatch, n):
    def forbidden(*a, **k): raise AssertionError('No real model/network calls')
    monkeypatch.setattr(urllib.request, 'urlopen', forbidden)
    final, prepared, context, _ = prepared_context(tmp_path, n)
    imported = main.import_dataset(repo, final)
    before_import = snapshot(repo)
    assert main.import_dataset(repo, final) == imported
    assert snapshot(repo) == before_import
    ds = imported['dataset_id']
    authorization = authorize(tmp_path, final, prepared, context, ds, db)
    receipt = main.materialize(repo, final, prepared, context, authorization, dataset_id=ds, database=db)
    assert receipt['planned_runs'] == n*9 and receipt['seeds'] == [101, 202, 303]
    assert receipt['models'] == 3 and receipt['attempts'] == receipt['predictions'] == receipt['model_calls'] == 0
    exp = receipt['experiment_id']
    setup = json.loads(repo.file(repo._row('experiments', exp)['setup_file_id']))
    assert setup['runtime']['runtime_identity'].startswith('evaluation_v2_')
    assert setup['output_interface']['mode'] == 'format_json'
    assert len(setup['context_proofs']) == n*9
    assert len({i['logical_identity_sha256'] for i in setup['request_inventory']}) == n*9
    assert [repo._row('models', s['model_id'])['name'] for s in setup['schedule'][:9:3]] == list(request.MODELS)
    assert all(repo.file(i['file_id']) for i in setup['request_inventory'])
    assert not rows(repo, 'run_attempts') and not rows(repo, 'predictions')
    assert all(r['request_file_id'] is r['result'] is r['started_at'] is None for r in rows(repo, 'experiment_runs'))
    state = snapshot(repo)
    plan = batch.preflight(repo, ds, exp, database=db, root=tmp_path, live_check=lambda *a: True)
    assert plan.summary['planned'] == n*9 and plan.summary['problematic'] == 0
    assert plan.summary['token_limit'] == 512 and plan.summary['prompt'] == 'P2'
    assert snapshot(repo) == state
    with pytest.raises(ValueError, match='already materialized'):
        main.materialize(repo, final, prepared, context, authorization, dataset_id=ds, database=db)
    assert snapshot(repo) == state


def test_failed_authorization_and_missing_reference_roll_back(repo, db, tmp_path):
    final, prepared, context, _ = prepared_context(tmp_path)
    imported = main.import_dataset(repo, final)
    ds = imported['dataset_id']
    authorization = authorize(tmp_path, final, prepared, context, ds+1, db)
    state = snapshot(repo)
    with pytest.raises(ValueError, match='binding mismatch'):
        main.materialize(repo, final, prepared, context, authorization, dataset_id=ds, database=db)
    assert snapshot(repo) == state
    authorization = authorize(tmp_path, final, prepared, context, ds, db)
    # Direct corruption solely in this disposable fixture must not be silently repaired.
    repo.cn.execute('UPDATE dbo.dataset_cases SET reference_id=NULL WHERE dataset_id=?', ds)
    repo.cn.commit()
    state = snapshot(repo)
    with pytest.raises(ValueError):
        main.materialize(repo, final, prepared, context, authorization, dataset_id=ds, database=db)
    assert snapshot(repo) == state
    assert not rows(repo, 'experiments') and not rows(repo, 'predictions')
