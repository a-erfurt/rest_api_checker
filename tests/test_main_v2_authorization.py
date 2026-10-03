"""No real providers: validate the independent plan and execution boundaries."""
import json

import pytest

from rest_api_checker import cli, terminal, evaluation_batch_v2 as batch
from rest_api_checker.experiment.encoding import encode
from test_evaluation_batch_v2 import prepared, change_setup, preflight


@pytest.mark.parametrize('entry', ['cli', 'executor'])
def test_plan_only_refuses_before_prompt_provider_or_attempt(prepared, monkeypatch, entry):
    repo, root = prepared
    repo.files[9] = repo.files[10]
    plan = preflight(prepared, live_check=lambda *a: True)
    assert plan.summary['execution_authorized'] is False
    assert batch.inspect_plan(repo, 1, 1, database='TEST ONLY').summary['remaining'] == 9
    monkeypatch.setattr(batch, 'OllamaClient', lambda **k: pytest.fail('Provider constructed'))
    monkeypatch.setattr('builtins.input', lambda: pytest.fail('Execution consent must not be prompted'))
    monkeypatch.setattr(batch, 'preflight', lambda *a, **k: plan)
    with pytest.raises(ValueError, match='Main execution is not authorized'):
        if entry == 'executor':
            batch.execute(repo, plan, root=root, spool=root/'spool', resume=False, notify=lambda e: None)
        else:
            args = cli.arguments().parse_args(['experiment', 'run-batch', '1', '--dataset-id', '1', '--yes'])
            cli._batch_v2(repo, args, terminal.console(plain=True))
    assert repo.writes == 0 and not repo.tables.get('run_attempts') and not repo.tables.get('predictions')


@pytest.mark.parametrize('field', ['schedule', 'models', 'runtime', 'context_proofs', 'request_inventory',
                                  'output_interface', 'request_builder_sha256', 'parser_sha256', 'renderer_sha256'])
def test_any_setup_identity_drift_after_human_authorization_blocks(prepared, field):
    repo, root = prepared
    plan = preflight(prepared, live_check=lambda *a: True)
    change_setup(repo, lambda s: s.update({field: 'CHANGED AFTER AUTHORIZATION'}))
    with pytest.raises(ValueError, match='Setup changed after preflight'):
        batch.execute(repo, plan, root=root, spool=root/'spool', resume=False, notify=lambda e: None)
    assert repo.writes == 0


@pytest.mark.parametrize('field', ['database', 'dataset_id', 'experiment_id', 'plan_setup_sha256', 'decision', 'author', 'accepted_at'])
def test_authorization_does_not_transfer_to_different_identity(prepared, field):
    repo, _ = prepared
    approval = json.loads(repo.files[11]); approval[field] = ''
    repo.files[11] = encode(approval)
    # Even with an updated transport hash, the accepted human binding must match.
    from rest_api_checker.experiment.encoding import digest
    change_setup(repo, lambda s: s['execution_authorization'].update(authorization_sha256=digest(repo.files[11])))
    with pytest.raises(ValueError):
        preflight(prepared, live_check=lambda *a: pytest.fail('Runtime must not be contacted'))
    assert repo.writes == 0


def test_bare_true_is_not_authorization(prepared):
    repo, _ = prepared
    repo.files[9] = repo.files[10]
    change_setup(repo, lambda s: s.update(execution_authorized=True))
    with pytest.raises(ValueError, match='Hash-bound'):
        preflight(prepared, live_check=lambda *a: pytest.fail('Runtime must not be contacted'))
