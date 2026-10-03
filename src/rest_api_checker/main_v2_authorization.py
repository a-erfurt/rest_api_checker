"""Separate human execution gate over the exact immutable, inspected Main-v2 plan."""
import json
from pathlib import Path

from . import freeze, main_v2_release as release
from .experiment.encoding import digest
from .persistence.database import json_bytes, require
from .persistence.inspection import bindings, rows


def execution_binding(plan_raw, dataset_id, experiment_id, database):
    return dict(format='main-v2-execution-authorization-v1', database=database,
        dataset_id=dataset_id, experiment_id=experiment_id, plan_setup_sha256=digest(plan_raw),
        authorizes=['execute_exact_main_v2_plan'], automatic_retries_authorized=False)


def verify(repo, experiment, setup, *, database):
    """Called before dispatch AND before reservation; a boolean alone is never consent."""
    require(setup.get('execution_authorized') is True, 'Main execution is not authorized.')
    gate = setup.get('execution_authorization')
    require(isinstance(gate, dict), 'Hash-bound Main execution authorization required')
    plan_raw = repo.file(gate['plan_file_id'])
    approval_raw = repo.file(gate['authorization_file_id'])
    require(digest(plan_raw) == gate['plan_sha256'] and digest(approval_raw) == gate['authorization_sha256'],
            'Execution authorization evidence drift')
    base = json.loads(plan_raw)
    require(base.get('execution_authorized') is False and base.get('plan_authorized') is True,
            'Plan-only materialization required before execution authorization')
    require(setup == {**base, 'execution_authorized': True, 'execution_authorization': gate},
            'Authorized plan identity drift')
    approval = json.loads(approval_raw)
    require(type(approval.get('accepted_at')) is str, 'Dated human execution authorization required')
    release.accepted(approval, 'AUTHORIZE_MAIN_V2_EXECUTION',
        execution_binding(plan_raw, experiment['dataset_id'], experiment['id'], database))
    require(setup['bindings'] == bindings(repo, experiment['dataset_id'], setup['schedule']),
            'Authorized dataset/reference/configuration drift')
    actual = sorted(rows(repo, 'experiment_runs', experiment_id=experiment['id']), key=lambda r: r['run_order'])
    require([{k: r[k] for k in slot} for r, slot in zip(actual, setup['schedule'], strict=True)] == setup['schedule'],
            'Authorized run order drift')
    repo.verify_closure(setup['files'])


def require_execution(repo, plan):
    exp = repo._row('experiments', plan.summary['experiment_id'])
    raw = repo.file(exp['setup_file_id'])
    require(digest(raw) == plan.summary['setup_sha256'], 'Setup changed after preflight')
    verify(repo, exp, json.loads(raw), database=plan.summary['database'])


def execution_template(repo, dataset_id, experiment_id, *, database, root, live_check=freeze.verify_live):
    from .evaluation_batch_v2 import preflight
    plan = preflight(repo, dataset_id, experiment_id, database=database, root=root, live_check=live_check)
    require(plan.setup.get('execution_authorized') is False and plan.setup.get('plan_authorized') is True,
            'An execution-unauthorized materialized plan is required')
    require(plan.summary['previously_complete'] == plan.summary['problematic'] == 0, 'Pristine plan required')
    raw = repo.file(plan.state['experiment']['setup_file_id'])
    return dict(decision='PENDING', author='', accepted_at='',
                **execution_binding(raw, dataset_id, experiment_id, database))


def authorize_execution(repo, dataset_id, experiment_id, authorization, *, database, root, live_check=freeze.verify_live):
    """Explicit later human action only. Archive new setup; retain original plan bytes."""
    require(repo.cn.execute("SELECT HAS_PERMS_BY_NAME('dbo.experiments','OBJECT','UPDATE','setup_file_id','COLUMN')").fetchval() == 1,
            'Execution authorization requires an owner credential for setup_file_id; application permissions remain unchanged')
    repo.cn.commit()
    with repo.dispatch_owner():
        template = execution_template(repo, dataset_id, experiment_id, database=database, root=root, live_check=live_check)
        approval_raw = Path(authorization).read_bytes()
        expected = {k: v for k, v in template.items() if k not in ('decision', 'author', 'accepted_at')}
        approval = json.loads(approval_raw)
        require(type(approval.get('accepted_at')) is str, 'Dated human execution authorization required')
        release.accepted(approval, 'AUTHORIZE_MAIN_V2_EXECUTION', expected)
        with repo.transaction():
            require(repo.cn.execute('SELECT DB_NAME()').fetchval() == database, 'Authorized database/connection mismatch')
            exp = repo._row('experiments', experiment_id)
            plan_raw = repo.file(exp['setup_file_id'])
            require(digest(plan_raw) == template['plan_setup_sha256'], 'Plan changed during authorization')
            base = json.loads(plan_raw)
            approval_id = repo.archive('main-v2-execution-authorization.json', approval_raw)
            gate = dict(plan_file_id=exp['setup_file_id'], plan_sha256=digest(plan_raw),
                        authorization_file_id=approval_id, authorization_sha256=digest(approval_raw))
            setup = {**base, 'execution_authorized': True, 'execution_authorization': gate}
            verify(repo, exp, setup, database=database)
            require(not any(rows(repo, 'run_attempts', run_id=r['id']) for r in
                            rows(repo, 'experiment_runs', experiment_id=experiment_id)), 'Attempts already exist')
            setup_raw = json_bytes(setup)
            setup_id = repo.archive('main-v2-authorized-execution-setup.json', setup_raw)
            repo.cn.execute('UPDATE dbo.experiments SET setup_file_id=? WHERE id=? AND setup_file_id=?',
                            setup_id, experiment_id, exp['setup_file_id'])
            return dict(experiment_id=experiment_id, dataset_id=dataset_id, execution_authorized=True,
                        plan_setup_sha256=digest(plan_raw), setup_sha256=digest(setup_raw), model_calls=0)
