"""SELECT-only web projections; SQL fixtures are fabricated and explicitly opt-in."""
from hashlib import sha256
import json

import pyodbc
import pytest

from rest_api_checker.persistence.database import json_bytes
from rest_api_checker.web.queries import DataUnavailable, NotFound, WebQueries, _text
from .conftest import outcome


class SelectConnection:
    """Fail immediately if a UI read attempts any transaction or write action."""

    def __init__(self, connection):
        self.connection = connection
        self.statements = []

    def execute(self, statement, *parameters):
        assert statement.lstrip().upper().startswith('SELECT '), statement
        self.statements.append((statement, parameters))
        return self.connection.execute(statement, *parameters)


def settle(repo, planned, result='valid', response=b'<script>hostile fixture</script>'):
    request = b'{"messages":[{"content":"fabricated stored context"}]}'
    attempt = repo.reserve(planned['run'], request, attempt=1)
    repo.observe_start(attempt, '2026-09-26T12:00:00+05:45')
    repo.finalize(attempt, **outcome(repo, attempt, result, retry=result == 'technical_failure', response=response))
    if result == 'technical_failure':
        attempt = repo.reserve(planned['run'], request, attempt=2)
        repo.finalize(attempt, **outcome(repo, attempt, result, response=response))
    repo.complete_experiment(planned['experiment'], finished_at='2026-09-26T12:02:00+05:45')


def test_query_rejects_write_and_sanitizes_database_errors():
    class BrokenConnection:
        def execute(self, *args):
            raise pyodbc.OperationalError('secret-password and connection-string')
    query = WebQueries(BrokenConnection())
    with pytest.raises(ValueError, match='SELECT'):
        query._rows('UPDATE dbo.experiments SET name=?', 'forbidden')
    with pytest.raises(DataUnavailable) as failure:
        query.experiments()
    assert 'secret-password' not in str(failure.value)


def test_pagination_bounds_and_literal_case_search():
    query = WebQueries(None)
    for page, size in [(0, 50), (1, 0), (1, 201), (True, 50)]:
        with pytest.raises(ValueError):
            query.runs(page=page, page_size=size)
    clause, parameters = query._run_filters(7, 8, 9, 'pending', "case%_[~'", 2)
    assert parameters == [7, 8, 9, 2, "%case~%~_~[~~'%"]
    assert 'r.result IS NULL' in clause and "ESCAPE '~'" in clause
    assert "case%" not in clause
    with pytest.raises(ValueError):
        query._run_filters(None, None, None, 'invented', '', None)


def test_binary_view_is_lossless_and_empty_is_distinct():
    assert _text(b'') == ''
    assert _text(b'\xff\x00') == 'Non-UTF-8 bytes; exact base64:\n/wA='


def test_dataset_relationship_limit_is_explicit():
    class BoundedDatasetQueries(WebQueries):
        def _one(self, statement, *parameters):
            return dict(id=1, name='FABRICATED large dataset', version='v1', purpose='development') if 'dbo.datasets' in statement else dict(total=205)

        def _rows(self, statement, *parameters):
            assert 'TOP (200)' in statement
            return [dict(case_id=n, case_code=f'FAB-{n}', reference_id=n, position=n) for n in range(1, 201)]

    detail = BoundedDatasetQueries(None).data_detail('datasets', 1)
    assert detail['metadata']['Cases'] == 205
    assert detail['metadata']['Case links shown'].startswith('First 200 of 205')
    assert len(detail['relationships']) == 200


@pytest.mark.sqlserver
def test_empty_database_and_missing_records(repo):
    query = WebQueries(SelectConnection(repo.cn))
    assert query.schema_version() == 2
    assert query.experiments() == []
    assert query.runs()['total'] == 0
    assert query.data_list('datasets')['items'] == []
    assert query.filter_options() == dict(models=[], prompts=[])
    with pytest.raises(NotFound):
        query.run_detail(999)
    with pytest.raises(NotFound):
        query.data_detail('cases', 999)


@pytest.mark.sqlserver
def test_pending_running_completed_and_report_gate(repo, planned):
    cn = SelectConnection(repo.cn)
    query = WebQueries(cn)
    experiment = query.experiments()[0]
    assert experiment['state'] == 'planned' and experiment['fabricated'] is True
    assert (experiment['planned'], experiment['completed'], experiment['pending']) == (1, 0, 1)
    assert query.overview(planned['experiment'])['recent_runs'] == []
    assert query.report(planned['experiment']) is None
    detail = query.run_detail(planned['run'])
    assert detail['prediction'] is None and detail['attempts'] == [] and detail['evidence'] == []
    attempt = repo.reserve(planned['run'], b'fabricated request', attempt=1)
    # Reservation alone is not evidence that the experiment started.
    assert query.experiments()[0]['state'] == 'planned'
    repo.observe_start(attempt, '2026-09-26T12:00:00+05:45')
    assert query.experiments()[0]['state'] == 'running'
    assert query.report(planned['experiment']) is None
    repo.finalize(attempt, **outcome(repo, attempt))
    assert query.experiments()[0]['state'] == 'running'
    assert query.report(planned['experiment']) is None  # finished_at is required as well as all outcomes.
    repo.complete_experiment(planned['experiment'], finished_at='2026-09-26T12:02:00+05:45')
    assert query.experiments()[0]['state'] == 'completed'
    assert query.report(planned['experiment']) is None  # Opening a page does not create a report.
    assert repo.cn.execute('SELECT COUNT(*) FROM dbo.evaluation_reports').fetchval() == 0
    assert all(sql.lstrip().upper().startswith('SELECT ') for sql, _ in cn.statements)


@pytest.mark.sqlserver
@pytest.mark.parametrize('result', ['valid', 'parser_failure', 'technical_failure'])
def test_outcome_detail_evidence_and_attention(repo, planned, result):
    settle(repo, planned, result)
    cn = SelectConnection(repo.cn)
    query = WebQueries(cn)
    overview = query.overview(planned['experiment'])
    assert overview['experiment'][result] == 1 and overview['experiment']['pending'] == 0
    assert overview['recent_runs'][0]['result'] == result
    detail = query.run_detail(planned['run'])
    assert detail['run']['case'] == 'fixture-case'
    assert detail['reference']['c1'] == 'PASS'
    if result == 'valid':
        assert [detail['prediction'][c] for c in ('c1', 'c2', 'c3')] == ['FAIL', 'PASS', 'NOT_APPLICABLE']
        assert detail['prediction']['c2_reason'] == ' fabricated C2 '
    else:
        assert detail['prediction'] is None
    assert query.runs(status='attention')['total'] == (0 if result == 'valid' else 1)
    assert query.runs(status=result)['total'] == 1
    assert query.runs(status='pending')['total'] == 0
    response = query.run_detail(planned['run'], tab='response')
    assert response['run']['response']['status_code'] == 200
    assert response['evidence'][0]['content'] == '{"fixture":true}'
    contract = query.run_detail(planned['run'], tab='openapi')
    assert json.loads(contract['evidence'][0]['content'])['openapi'] == '3.1.0'
    assert 'fabricated stored context' in contract['evidence'][1]['content']
    assert query.run_detail(planned['run'], tab='raw')['evidence'][0]['content'] == '<script>hostile fixture</script>'
    assert 'fabricated outcome' in query.run_detail(planned['run'], tab='attempts')['evidence'][-2]['content']
    assert len(detail['attempts']) == (2 if result == 'technical_failure' else 1)


@pytest.mark.sqlserver
def test_server_pagination_filters_search_and_list_query_cost(repo, planned):
    schedule = [{**planned['schedule'][0], 'repetition': n, 'run_order': n} for n in range(1, 58)]
    setup = {**planned['setup'], 'schedule': schedule}
    experiment, runs = repo.plan_experiment(name='FABRICATED paginated query fixture', kind='comparison',
        dataset_id=planned['dataset'], schedule_seed=setup['schedule_seed'], setup=setup, schedule=schedule)
    cn = SelectConnection(repo.cn)
    query = WebQueries(cn)
    first = query.runs(experiment_id=experiment)
    assert first['total'] == 57 and first['pages'] == 2 and len(first['items']) == 50
    assert len(cn.statements) == 2
    assert 'OFFSET ? ROWS FETCH NEXT ? ROWS ONLY' in cn.statements[-1][0]
    assert all('f.content' not in sql and 'c1_reason' not in sql for sql, _ in cn.statements)
    second = query.runs(experiment_id=experiment, page=2)
    assert [r['id'] for r in second['items']] == runs[50:]
    assert query.runs(experiment_id=experiment, model_id=planned['model'], prompt_id=planned['prompt'],
                      status='pending', search='fixture-case', repetition=3)['total'] == 1
    assert query.runs(experiment_id=experiment, search='%')['total'] == 0
    assert query.runs(experiment_id=experiment, search="' OR 1=1 --")['total'] == 0
    assert query.runs(experiment_id=experiment, model_id=999)['total'] == 0
    assert query.filter_options(experiment)['models'] == [dict(id=planned['model'], name='fabricated-model')]


@pytest.mark.sqlserver
def test_data_tables_details_and_reference_source(repo, planned):
    cn = SelectConnection(repo.cn)
    query = WebQueries(cn)
    assert query.data_list('datasets')['items'][0]['case_count'] == 1
    case = query.data_list('cases')['items'][0]
    assert case['case'] == 'fixture-case' and case['operation'] == 'POST /items'
    assert case['c1'] == 'PASS' and case['reference_id'] == planned['case']['reference_id']
    references = query.data_list('references')['items']
    assert references[0]['version'] == 1
    dataset = query.data_detail('datasets', planned['dataset'])
    assert dataset['metadata']['Cases'] == 1 and 'Dataset ID' in dataset['technical']
    case_detail = query.data_detail('cases', planned['case']['case_id'])
    assert case_detail['evidence'][0]['content'] == '{"fixture":true}'
    assert case_detail['metadata']['C1'] == 'PASS'
    assert case_detail['metadata']['Reference binding'] == 'Revision 1'
    assert case_detail['technical']['Body SHA-256'] == sha256(b'{"fixture":true}').hexdigest()
    assert len(case_detail['relationships']) == 3
    reference = query.data_detail('references', planned['case']['reference_id'])
    assert reference['metadata']['Selected response branch'] == '200'
    assert reference['metadata']['Selected media type'] == 'application/json'
    for kind, id in [('models', planned['model']), ('prompts', planned['prompt']), ('configs', planned['config']),
                     ('contracts', planned['case']['contract']), ('files', planned['case']['source_id']),
                     ('experiments', planned['experiment'])]:
        listed = query.data_list('artifacts', kind=kind)
        assert listed['total'] >= 1
        assert all('content' not in item for item in listed['items'])
        detail = query.data_detail('artifacts', id, kind=kind)
        assert detail['technical']['Id'] == id
    assert query.data_list('artifacts', kind='reports')['items'] == []
    with pytest.raises(NotFound):
        query.data_list('artifacts', kind='files; DELETE dbo.files')


@pytest.mark.sqlserver
def test_reads_exact_persisted_report_without_evaluation(repo, planned):
    settle(repo, planned)
    raw_input = json_bytes(dict(experiment_id=planned['experiment'], files=planned['setup']['files'],
                               references=[], fabricated=True))
    input_id = repo.archive('FABRICATED ui analysis input', raw_input)
    expected = dict(format='comparison-evaluation-v1', experiment_id=planned['experiment'],
        input_sha256=sha256(raw_input).hexdigest(), fabricated=True, selected_prompt='P2',
        metrics={'P2': {'Score': {'numerator': 123, 'denominator': 324, 'value': '41/108'}}})
    file_id = repo.archive('FABRICATED ui report', json_bytes(expected))
    report_id = repo.report(experiment_id=planned['experiment'], input_file_id=input_id, file_id=file_id,
                          code_version='FABRICATED UI TEST')
    cn = SelectConnection(repo.cn)
    query = WebQueries(cn)
    assert query.report(planned['experiment']) == expected
    assert query.data_list('artifacts', kind='reports')['items'][0]['id'] == report_id
    assert query.data_detail('artifacts', report_id, kind='reports')['technical']['Code version'] == 'FABRICATED UI TEST'
    assert repo.cn.execute('SELECT COUNT(*) FROM dbo.evaluation_reports').fetchval() == 1


@pytest.mark.sqlserver
def test_ambiguous_reference_binding_is_not_silently_replaced(repo, planned):
    original = planned['case']['reference_id']
    case = planned['case']['case_id']
    source = repo.archive('FABRICATED reference revision source',
                          json_bytes({**planned['case']['source'], 'fixture_revision': 2}))
    revision = repo.reference(case, 2, source, '/oracle', notes='FABRICATED alternative revision')
    dataset = repo.dataset('second-fabricated-dataset', 'v1', 'development')
    repo.membership(dataset, case, revision, 'fixture-case', 1)
    query = WebQueries(SelectConnection(repo.cn))
    listed = query.data_list('cases')['items'][0]
    assert listed['reference_id'] is None and listed['c1'] is None
    # An experiment still retains its original explicitly bound reference.
    assert query.run_detail(planned['run'])['reference']['id'] == original
    assert len(query.data_list('references')['items']) == 2
    assert query.data_detail('cases', case)['metadata']['C1'] is None


@pytest.mark.sqlserver
def test_unbound_membership_does_not_inherit_another_datasets_reference(repo, planned):
    case = planned['case']['case_id']
    dataset = repo.dataset('FABRICATED unbound dataset', 'v1', 'development')
    repo.membership(dataset, case, None, 'fixture-unbound', 1)
    query = WebQueries(SelectConnection(repo.cn))
    row = query.data_list('cases')['items'][0]
    assert row['reference_id'] is None and row['c1'] is None
    assert query.data_detail('cases', case)['metadata']['C1'] is None
    assert query.run_detail(planned['run'])['reference']['id'] == planned['case']['reference_id']
