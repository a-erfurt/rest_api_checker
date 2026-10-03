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
    # Exercise materialization with the actual application role, not SA privileges.
    repo.cn.execute('CREATE USER [main_v2_test_application] WITHOUT LOGIN')
    repo.cn.execute('ALTER ROLE [rac_application] ADD MEMBER [main_v2_test_application]')
    repo.cn.execute('EXECUTE AS USER = \'main_v2_test_application\'')
    repo.cn.commit()
    receipt = main.materialize(repo, final, prepared, context, authorization, dataset_id=ds, database=db)
    assert receipt['planned_runs'] == n*9 and receipt['seeds'] == [101, 202, 303]
    assert receipt['models'] == 3 and receipt['attempts'] == receipt['predictions'] == receipt['model_calls'] == 0
    exp = receipt['experiment_id']
    setup = json.loads(repo.file(repo._row('experiments', exp)['setup_file_id']))
    assert setup['runtime']['runtime_identity'].startswith('evaluation_v2_')
    assert setup['output_interface']['mode'] == 'format_json'
    assert setup['plan_authorized'] is True and setup['execution_authorized'] is False
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
    repo.cn.execute('REVERT')
    repo.cn.commit()
    with pytest.raises(ValueError, match='Main execution is not authorized'):
        batch.execute(repo, plan, root=tmp_path, spool=tmp_path/'spool', resume=False,
                      notify=lambda e: None, client=object())
    # Direct lower-level reservation must not bypass the CLI gate.
    with pytest.raises(ValueError, match='Main execution is not authorized'):
        repo.reserve(plan.state['runs'][0]['id'], next(iter(plan.requests.values())).body, attempt=1)
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


def test_separate_execution_authorization_is_bound_to_inspected_plan(repo, db, tmp_path, monkeypatch):
    from rest_api_checker import main_v2_authorization as gate, cli, terminal
    from rest_api_checker.experiment.encoding import encode
    final, prepared, context, _ = prepared_context(tmp_path)
    ds = main.import_dataset(repo, final)['dataset_id']
    authorization = authorize(tmp_path, final, prepared, context, ds, db)
    receipt = main.materialize(repo, final, prepared, context, authorization, dataset_id=ds, database=db)
    exp = receipt['experiment_id']
    before = snapshot(repo)
    original = batch.preflight
    monkeypatch.setattr(batch, 'preflight', lambda *a, **k: original(*a, **{**k, 'live_check': lambda *a: True}))
    for command, extra in [('batch-status', []), ('run-batch', ['--dry-run'])]:
        args = cli.arguments().parse_args(['--database', db, '--root', str(tmp_path), 'experiment', command,
            str(exp), '--dataset-id', str(ds), '--json', *extra])
        result, code = cli._batch_v2(repo, args, terminal.console())
        assert code == 0 and result['plan']['execution_authorized'] is False
        assert result['plan']['planned'] == result['plan']['remaining'] == 9
        assert result['plan']['previously_complete'] == result['plan']['problematic'] == 0
    assert snapshot(repo) == before
    pending = gate.execution_template(repo, ds, exp, database=db, root=tmp_path)
    path = tmp_path/'FABRICATED-execution-authorization.json'
    path.write_bytes(encode(pending))
    with pytest.raises(ValueError, match='Explicit human'):
        gate.authorize_execution(repo, ds, exp, path, database=db, root=tmp_path)
    assert snapshot(repo) == before
    approved = {**pending, 'decision': 'AUTHORIZE_MAIN_V2_EXECUTION', 'author': 'FABRICATED TEST ONLY',
                'accepted_at': '2026-10-03T12:00:00+02:00'}
    path.write_bytes(encode({**approved, 'plan_setup_sha256': '0'*64}))
    with pytest.raises(ValueError, match='binding mismatch'):
        gate.authorize_execution(repo, ds, exp, path, database=db, root=tmp_path)
    assert snapshot(repo) == before
    path.write_bytes(encode(approved))
    repo.cn.execute('CREATE USER [main_v2_gate_application] WITHOUT LOGIN')
    repo.cn.execute('ALTER ROLE [rac_application] ADD MEMBER [main_v2_gate_application]')
    repo.cn.execute('EXECUTE AS USER = \'main_v2_gate_application\'')
    repo.cn.commit()
    with pytest.raises(ValueError, match='requires an owner credential'):
        gate.authorize_execution(repo, ds, exp, path, database=db, root=tmp_path)
    repo.cn.execute('REVERT')
    repo.cn.commit()
    assert snapshot(repo) == before
    result = gate.authorize_execution(repo, ds, exp, path, database=db, root=tmp_path)
    assert result['plan_setup_sha256'] == receipt['setup_sha256']
    assert not rows(repo, 'run_attempts') and not rows(repo, 'predictions')
    plan = batch.preflight(repo, ds, exp, database=db, root=tmp_path)
    assert plan.summary['execution_authorized'] is True  # Disposable fabricated fixture only.
    exp_row = repo._row('experiments', exp)
    changed = json.loads(repo.file(exp_row['setup_file_id']))
    changed['runtime']['ollama']['version'] = 'UNQUALIFIED DRIFT'
    changed_id = repo.archive('FABRICATED-drift.json', encode(changed))
    repo.cn.execute('UPDATE dbo.experiments SET setup_file_id=? WHERE id=?', changed_id, exp)
    repo.cn.commit()
    calls = []
    monkeypatch.setattr(batch, 'OllamaClient', lambda **k: calls.append(k))
    with pytest.raises(ValueError, match='Setup changed'):
        batch.execute(repo, plan, root=tmp_path, spool=tmp_path/'spool', resume=False, notify=lambda e: None)
    with pytest.raises(ValueError, match='Authorized plan identity drift'):
        repo.reserve(plan.state['runs'][0]['id'], next(iter(plan.requests.values())).body, attempt=1)
    assert not calls and not rows(repo, 'run_attempts') and not rows(repo, 'predictions')
