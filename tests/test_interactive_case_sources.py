"""Read-only final source selection and isolated execution with fabricated rows."""
from copy import deepcopy
import json

import pytest

from rest_api_checker import live_demo as demo, live_adhoc_runtime as adhoc
from rest_api_checker.experiment import batch
from rest_api_checker.persistence.inspection import bindings
from test_live_demo import repository  # noqa: F401; fabricated in-memory repository
from test_live_adhoc_runtime import api_for


def test_interactive_catalog_prefers_final_and_preserves_strict_direct_selection(repository):
    before = deepcopy(repository.tables), dict(repository.files)
    inventory = demo.catalog(repository, adhoc=True)
    assert inventory['default_dataset_id'] == 3
    assert [item['id'] for item in inventory['case_sets']] == [3, 4, 1]
    assert inventory['case_sets'][0]['label'] == 'Final evaluation'
    assert {row['id'] for row in inventory['cases']} == {21, 22, 23, 24}
    final = next(row for row in inventory['cases'] if row['id'] == 23)
    assert final['case_id'] == final['reference_id'] == 13
    assert final['is_final_case_set'] and final['case_set_label'] == 'Final evaluation'
    assert [row['id'] for row in demo.catalog(repository)['cases']] == [21]
    assert (repository.tables, repository.files) == before and repository.writes == []


def test_final_default_is_derived_from_evaluation_purpose_if_protected_set_absent(repository):
    del repository.tables['dataset_cases'][23]
    assert demo.catalog(repository, adhoc=True)['default_dataset_id'] == 4
    del repository.tables['dataset_cases'][24]
    inventory = demo.catalog(repository, adhoc=True)
    assert inventory['default_dataset_id'] == 1
    assert inventory['case_sets'][0]['label'] == 'Development'


def test_incomplete_final_source_never_becomes_default(repository):
    repository.tables['dataset_cases'][23]['reference_id'] = None
    inventory = demo.catalog(repository, adhoc=True)
    assert inventory['default_dataset_id'] == 4
    assert all(row['dataset_id'] != 3 for row in inventory['cases'])


def test_saved_interactive_contexts_are_not_offered_as_case_sets(repository):
    repository.add('datasets', id=7, name=demo.INTERACTIVE_DATASET_PREFIX+'FABRICATED',
                   version='v1', purpose='development')
    repository.add('dataset_cases', id=27, dataset_id=7, case_id=11, reference_id=11,
                   case_code='CASE-11', position=1)
    for adhoc_mode in (False, True):
        inventory = demo.catalog(repository, adhoc=adhoc_mode)
        assert 7 not in {row['id'] for row in inventory['case_sets']}
        assert 27 not in {row['id'] for row in inventory['cases']}


@pytest.mark.parametrize('case_id', [22, 23, 24])
def test_final_source_plan_has_no_writes_or_runtime_probe(repository, tmp_path, monkeypatch, case_id):
    before = deepcopy(repository.tables), dict(repository.files)
    monkeypatch.setattr(adhoc, 'metadata', lambda *args: pytest.fail('Planning contacted runtime'))
    plan = demo.plan(repository, case_id=case_id, model_ids=[1], repetitions=1, root=tmp_path, adhoc=True)
    assert plan.schedule[0]['dataset_case_id'] == case_id
    assert plan.snapshot == bindings(repository, plan.summary['dataset_id'], plan.schedule)
    assert plan.summary['scientific_evaluation'] is False
    assert (repository.tables, repository.files) == before and repository.writes == []
    with pytest.raises(ValueError, match='eligible'):
        demo.plan(repository, case_id=case_id, model_ids=[1], repetitions=1, root=tmp_path)


@pytest.mark.parametrize('change', ['reference', 'response', 'membership'])
def test_final_source_drift_blocks_before_runtime_or_new_context(repository, tmp_path, change):
    plan = demo.plan(repository, case_id=23, model_ids=[1], repetitions=1, root=tmp_path, adhoc=True)
    if change == 'reference':
        repository.tables['reference_results'][13]['c1'] = 'FAIL'
    elif change == 'response':
        repository.files[3] = b'{"changed":true}'
    else:
        repository.tables['dataset_cases'][23]['case_code'] = 'changed'
    with pytest.raises(ValueError):
        demo.execute(repository, plan, root=tmp_path, spool=tmp_path/'spool',
                     runtime_api=lambda *args: pytest.fail('Drift must block before runtime'))
    assert repository.writes == []


@pytest.mark.parametrize('source_dataset_id,case_id', [(3, 23), (4, 24)])
def test_final_case_execution_only_allocates_separate_context(repository, tmp_path, monkeypatch,
                                                            source_dataset_id, case_id):
    repository.tables['datasets'][3]['purpose'] = 'evaluation'
    repository.add('experiments', id=10003, dataset_id=3, name='FABRICATED protected experiment')
    repository.add('experiment_runs', id=10101, experiment_id=10003, dataset_id=3,
                   dataset_case_id=23, result='valid')
    original_tables, original_files = deepcopy(repository.tables), dict(repository.files)
    plan = demo.plan(repository, case_id=case_id, model_ids=[1], repetitions=3, root=tmp_path, adhoc=True)
    original_plan_schedule = deepcopy(plan.schedule)

    def dataset(name, version, purpose):
        new_id = max(repository.tables['datasets']) + 1
        repository.add('datasets', id=new_id, name=name, version=version, purpose=purpose)
        repository.writes.append(('dataset', new_id))
        return new_id

    def membership(dataset_id, selected_case_id, reference_id, case_code, position):
        new_id = max(repository.tables['dataset_cases']) + 1
        repository.add('dataset_cases', id=new_id, dataset_id=dataset_id, case_id=selected_case_id,
                       reference_id=reference_id, case_code=case_code, position=position)
        repository.writes.append(('membership', new_id))
        return new_id

    monkeypatch.setattr(repository, 'dataset', dataset, raising=False)
    monkeypatch.setattr(repository, 'membership', membership, raising=False)
    dispatched = []

    def attempt(repo, run_id, **kwargs):
        inputs, request = kwargs['prepare_request'](repo, run_id)
        run = inputs['run']
        assert run['dataset_id'] not in (3, source_dataset_id)
        assert repo._row('datasets', run['dataset_id'])['purpose'] == 'development'
        assert kwargs['verify_runtime'](request, kwargs['context_proof']) is True
        assert isinstance(kwargs['client'], adhoc.AdhocClient)
        assert kwargs['client'].dataset_id == run['dataset_id']
        assert request == plan.requests[run['run_order']]
        dispatched.append(run_id)
        repo.tables['experiment_runs'][run_id].update(result='parser_failure', request_file_id=1)
        repo.add('run_attempts', id=run_id, run_id=run_id, attempt=1, result='parser_failure',
                 response_file_id=3, diagnostics_file_id=None, duration_ms=7)

    monkeypatch.setattr(batch, 'execute_attempt', attempt)
    result = demo.execute(repository, plan, root=tmp_path, spool=tmp_path/'spool',
                          runtime_api=api_for(repository), client=object())
    assert result['status'] == 'COMPLETED', result
    assert len(dispatched) == 3
    assert result['experiment_id'] != 10003
    assert plan.schedule == original_plan_schedule and plan.summary['dataset_id'] == source_dataset_id
    experiment = repository._row('experiments', result['experiment_id'])
    setup = json.loads(repository.file(experiment['setup_file_id']))
    assert setup['dataset_id'] not in (3, source_dataset_id)
    assert setup['scientific_evaluation'] is False and setup['gate_b_complete'] is False
    source = setup['source_selection']
    assert source == dict(dataset_id=source_dataset_id, dataset_case_id=case_id,
                          read_only=True, bindings=plan.snapshot)
    member = setup['bindings']['dataset_cases'][0]
    old_member = original_tables['dataset_cases'][case_id]
    assert member['case_id'] == old_member['case_id']
    assert member['reference_id'] == old_member['reference_id']
    assert member['id'] != old_member['id']
    assert len([action for action, _ in repository.writes if action == 'dataset']) == 1
    assert len([action for action, _ in repository.writes if action == 'membership']) == 1
    for table, records in original_tables.items():
        assert {row_id: repository.tables[table][row_id] for row_id in records} == records
    assert {file_id: repository.files[file_id] for file_id in original_files} == original_files
    assert demo.catalog(repository, adhoc=True)['default_dataset_id'] == 3
    assert setup['dataset_id'] not in {item['id'] for item in demo.catalog(repository, adhoc=True)['case_sets']}


def test_final_runtime_failure_never_creates_context_dataset(repository, tmp_path):
    plan = demo.plan(repository, case_id=23, model_ids=[1], repetitions=1, root=tmp_path, adhoc=True)
    api = api_for(repository)

    def missing_model(path, data=None):
        return {'models': []} if path == '/api/tags' else api(path, data)

    with pytest.raises(ValueError, match='not installed'):
        demo.execute(repository, plan, root=tmp_path, spool=tmp_path/'spool', runtime_api=missing_model)
    assert repository.writes == []
