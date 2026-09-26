"""Bounded read projections and content-bound setup identities; no arbitrary SQL UI."""
from decimal import Decimal
from hashlib import sha256
import json

from .database import require
from .repository import TABLES


def portable(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {k: portable(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [portable(v) for v in value]
    return value


def rows(repo, table, **filters):
    require(table in TABLES, 'Unknown inspection table')
    require(set(filters) <= set(repo._columns[table]), 'Unknown filter')
    clause = ' AND '.join(f'{k}=?' for k in filters) or '1=1'
    cur = repo.cn.execute(f'SELECT * FROM dbo.{table} WHERE {clause} ORDER BY id', *filters.values())
    return [dict(zip([d[0] for d in cur.description], row)) for row in cur.fetchall()]


def bindings(repo, dataset_id, schedule):
    """Capture exact relational values and file hashes before any dispatch."""
    result = {'datasets': [repo._row('datasets', dataset_id)],
              'dataset_cases': rows(repo, 'dataset_cases', dataset_id=dataset_id)}
    def collect(table, ids):
        result[table] = [repo._row(table, i) for i in sorted(set(ids))]
    collect('reference_results', [r['reference_id'] for r in result['dataset_cases']])
    collect('test_cases', [r['case_id'] for r in result['dataset_cases']])
    collect('responses', [r['response_id'] for r in result['test_cases']])
    collect('api_operations', [r['operation_id'] for r in result['test_cases']])
    collect('api_contracts', [r['contract_id'] for r in result['api_operations']])
    for table, key in [('models', 'model_id'), ('prompts', 'prompt_id'), ('run_configs', 'run_config_id')]:
        collect(table, [r[key] for r in schedule])
    files = {v for records in result.values() for r in records for k, v in r.items()
             if k.endswith('file_id') and v is not None}
    result['files'] = [dict(file_id=i, sha256=sha256(repo.file(i)).hexdigest()) for i in sorted(files)]
    return portable(result)


def status(repo, experiment_id):
    experiment = repo._row('experiments', experiment_id)
    setup = json.loads(repo.file(experiment['setup_file_id']))
    require(experiment['dataset_id']==setup['dataset_id'] and experiment['schedule_seed']==setup['schedule_seed'],
            'Experiment/setup identity drift')
    runs = sorted(rows(repo, 'experiment_runs', experiment_id=experiment_id), key=lambda r: r['run_order'])
    keys = ('dataset_case_id', 'model_id', 'prompt_id', 'run_config_id', 'repetition', 'seed', 'run_order')
    require([{k: r[k] for k in keys} for r in runs] == sorted(setup['schedule'], key=lambda r: r['run_order']),
            'Missing, unexpected, duplicate or drifted scheduled runs')
    counts = {k: sum(r['result'] == k for r in runs) for k in ('valid', 'parser_failure', 'technical_failure')}
    completed = sum(counts.values())
    return dict(experiment=experiment, fabricated=setup.get('fabricated') is True,
                planned=len(runs), completed=completed, pending=len(runs)-completed, counts=counts, runs=runs)


def run_detail(repo, run_id, *, raw=False):
    run = repo._row('experiment_runs', run_id)
    member = repo._row('dataset_cases', run['dataset_case_id'])
    reference = repo._row('reference_results', member['reference_id'])
    predictions = rows(repo, 'predictions', run_id=run_id)
    prediction = predictions[0] if predictions else None
    attempts = sorted(rows(repo, 'run_attempts', run_id=run_id), key=lambda r: r['attempt'])
    result = dict(run=run, case=member['case_code'], model=repo._row('models', run['model_id'])['name'],
                  prompt=repo._row('prompts', run['prompt_id'])['name'], reference=reference, prediction=prediction,
                  correctness={c: prediction[c] == reference[c] if prediction else None for c in ('c1','c2','c3')},
                  attempts=attempts)
    if raw:
        import base64
        from ..experiment.orchestration import prepare
        inputs, request = prepare(repo, run_id)
        result['raw'] = dict(request=json.loads(repo.file(run['request_file_id'])) if run['request_file_id'] else None,
                            evidence=json.loads(request.body)['messages'][1]['content'],
                            provider_envelopes=[dict(attempt=a['attempt'], base64=base64.b64encode(
                                repo.file(a['response_file_id'])).decode()) for a in attempts if a['response_file_id']])
    return portable(result)
