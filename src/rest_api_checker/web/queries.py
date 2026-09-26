"""Bounded SQL read projections for the research UI; no execution/write services.

Connections belong to a single request. The application rolls them back and closes
them; this module issues SELECT only, including for immutable evidence reads.
"""
from base64 import b64encode
from decimal import Decimal
from hashlib import sha256
import json

import pyodbc

from ..persistence.database import IntegrityViolation, pointer
from ..persistence.migrate import verify


class NotFound(LookupError):
    """The requested persisted record does not exist."""


class DataUnavailable(RuntimeError):
    """Public, credential-free explanation of unavailable persisted evidence."""


class ReportUnavailable(DataUnavailable):
    """A persisted evaluation cannot be presented as a supported bound report."""


def _portable(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {k: _portable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_portable(v) for v in value]
    return value


def _text(raw):
    """No lossy replacement: non-UTF-8 evidence is represented as exact base64."""
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError:
        return 'Non-UTF-8 bytes; exact base64:\n' + b64encode(raw).decode('ascii')


def _json_text(value):
    return json.dumps(_portable(value), ensure_ascii=False, indent=2)


def _page(page, page_size):
    if type(page) is not int or page < 1 or type(page_size) is not int or not 1 <= page_size <= 200:
        raise ValueError('Page must be positive and page size must be between 1 and 200')
    return (page - 1) * page_size


RUN_FROM = '''FROM dbo.experiment_runs r
    JOIN dbo.dataset_cases dc ON dc.id=r.dataset_case_id
    JOIN dbo.models m ON m.id=r.model_id
    JOIN dbo.prompts p ON p.id=r.prompt_id
    LEFT JOIN dbo.reference_results ref ON ref.id=dc.reference_id
    LEFT JOIN dbo.predictions pred ON pred.run_id=r.id
    OUTER APPLY (SELECT TOP (1) a.attempt,a.duration_ms,a.prepared_at
        FROM dbo.run_attempts a WHERE a.run_id=r.id ORDER BY a.attempt DESC) last_attempt'''
RUN_COLUMNS = '''r.id,r.experiment_id,dc.case_id,dc.case_code AS [case],r.model_id,m.name AS model,
    r.prompt_id,p.name AS prompt,r.repetition,r.seed,r.run_order,r.result,r.started_at,r.finished_at,
    last_attempt.attempt,last_attempt.duration_ms,last_attempt.prepared_at,
    ref.c1 AS reference_c1,ref.c2 AS reference_c2,ref.c3 AS reference_c3,
    pred.c1 AS prediction_c1,pred.c2 AS prediction_c2,pred.c3 AS prediction_c3'''

EXPERIMENT_SELECT = '''SELECT e.id,e.name,e.kind,e.dataset_id,d.name AS dataset_name,
    d.version AS dataset_version,d.purpose AS dataset_purpose,e.started_at,e.finished_at,
    counts.planned,counts.valid,counts.parser_failure,counts.technical_failure,
    JSON_VALUE(CASE WHEN ISJSON(CONVERT(VARCHAR(MAX),f.content))=1
        THEN CONVERT(VARCHAR(MAX),f.content) ELSE '{}' END,'$.fabricated') AS fabricated
    FROM dbo.experiments e JOIN dbo.datasets d ON d.id=e.dataset_id
    LEFT JOIN dbo.files f ON f.id=e.setup_file_id
    OUTER APPLY (SELECT COUNT_BIG(*) AS planned,
        COALESCE(SUM(CASE WHEN r.result='valid' THEN CAST(1 AS BIGINT) ELSE 0 END),0) AS valid,
        COALESCE(SUM(CASE WHEN r.result='parser_failure' THEN CAST(1 AS BIGINT) ELSE 0 END),0) AS parser_failure,
        COALESCE(SUM(CASE WHEN r.result='technical_failure' THEN CAST(1 AS BIGINT) ELSE 0 END),0) AS technical_failure
        FROM dbo.experiment_runs r WHERE r.experiment_id=e.id) counts'''

CASE_FROM = '''FROM dbo.test_cases tc
    JOIN dbo.api_operations op ON op.id=tc.operation_id
    JOIN dbo.api_contracts ac ON ac.id=op.contract_id
    JOIN dbo.apis api ON api.id=ac.api_id
    JOIN dbo.case_families fam ON fam.id=tc.family_id
    OUTER APPLY (SELECT CASE WHEN COUNT(DISTINCT dc.reference_id)=1
        AND COUNT(dc.reference_id)=COUNT(*)
        THEN MAX(dc.reference_id) END AS reference_id
        FROM dbo.dataset_cases dc WHERE dc.case_id=tc.id) binding
    LEFT JOIN dbo.reference_results ref ON ref.id=binding.reference_id'''

ARTIFACT_TABLES = {'models': 'models', 'prompts': 'prompts', 'configs': 'run_configs',
                   'contracts': 'api_contracts', 'files': 'files', 'experiments': 'experiments',
                   'reports': 'evaluation_reports'}
ARTIFACT_COLUMNS = {
    'models': 'id,name,family,parameters_b,quantization,context_length,digest,architecture,metadata_file_id',
    'prompts': 'id,name,version,strategy,file_id,parent_prompt_id',
    'configs': 'id,temperature,top_p,top_k,min_p,repeat_penalty,repeat_last_n,draft_num_predict,'
               'num_ctx,num_predict,think,stream,timeout_seconds',
    'contracts': 'id,api_id,openapi_version,file_id,imported_at',
    'files': 'id,name,sha256,size_bytes',
    'experiments': 'id,name,kind,dataset_id,setup_file_id,schedule_seed,started_at,finished_at,notes',
    'reports': 'id,experiment_id,baseline_report_id,created_at,code_version,input_file_id,file_id',
}


class WebQueries:
    """Routes receive this query surface, never a mutable persistence repository."""

    def __init__(self, connection):
        self._connection = connection

    def _rows(self, sql, *params):
        # All SQL is repository-owned. This guard also makes accidental writes fail closed.
        if not sql.lstrip().upper().startswith('SELECT '):
            raise ValueError('The web query layer only permits SELECT statements')
        try:
            cur = self._connection.execute(sql, *params)
            columns = [d[0] for d in cur.description]
            return [_portable(dict(zip(columns, row))) for row in cur.fetchall()]
        except pyodbc.Error as exc:
            raise DataUnavailable('Database unavailable. Check the local database configuration.') from exc

    def _one(self, sql, *params):
        rows = self._rows(sql, *params)
        if not rows:
            raise NotFound('The requested record was not found.')
        return rows[0]

    def schema_version(self):
        try:
            return verify(self._connection)
        except (pyodbc.Error, IntegrityViolation, OSError) as exc:
            raise DataUnavailable('Database schema unavailable or incompatible. Use the CLI to inspect it.') from exc

    def _file(self, file_id):
        if file_id is None:
            return None
        try:
            record = self._one('SELECT content,sha256,size_bytes FROM dbo.files WHERE id=?', file_id)
        except NotFound as exc:
            raise DataUnavailable('The persisted artifact is missing.') from exc
        raw = bytes(record['content'])
        if len(raw) != record['size_bytes'] or sha256(raw).hexdigest() != record['sha256']:
            raise DataUnavailable('The persisted artifact failed its integrity check.')
        return raw

    def _source(self, file_id, source_pointer):
        raw = self._file(file_id)
        if raw is None:
            return None
        try:
            return pointer(json.loads(raw), source_pointer)
        except (ValueError, TypeError) as exc:
            raise DataUnavailable('The persisted source record is unavailable or invalid.') from exc

    @staticmethod
    def _experiment(row):
        row['completed'] = row['valid'] + row['parser_failure'] + row['technical_failure']
        row['pending'] = row['planned'] - row['completed']
        row['fabricated'] = row['fabricated'] == 'true' if row['fabricated'] is not None else None
        if row['finished_at'] is not None:
            row['state'] = 'completed' if row['pending'] == 0 else 'incomplete'
        else:
            row['state'] = 'running' if row['started_at'] is not None else 'planned'
        return row

    def experiments(self):
        rows = self._rows(EXPERIMENT_SELECT + ''' ORDER BY
            CASE WHEN e.started_at IS NOT NULL AND e.finished_at IS NULL THEN 0
                 WHEN e.finished_at IS NOT NULL THEN 1 ELSE 2 END,
            e.finished_at DESC,e.started_at DESC,e.id DESC''')
        return [self._experiment(row) for row in rows]

    def _get_experiment(self, experiment_id):
        return self._experiment(self._one(EXPERIMENT_SELECT + ' WHERE e.id=?', experiment_id))

    def overview(self, experiment_id):
        experiment = self._get_experiment(experiment_id)
        recent = self._rows('SELECT TOP (5) ' + RUN_COLUMNS + ' ' + RUN_FROM + '''
            WHERE r.experiment_id=? AND (r.result IS NOT NULL OR last_attempt.attempt IS NOT NULL)
            ORDER BY COALESCE(r.finished_at,r.started_at,last_attempt.prepared_at) DESC,r.run_order DESC''', experiment_id)
        return dict(experiment=experiment, recent_runs=recent)

    @staticmethod
    def _run_filters(experiment_id, model_id, prompt_id, status, search, repetition):
        terms, parameters = [], []
        for column, value in [('r.experiment_id', experiment_id), ('r.model_id', model_id),
                              ('r.prompt_id', prompt_id), ('r.repetition', repetition)]:
            if value is not None:
                terms.append(column + '=?')
                parameters.append(value)
        if status:
            if status in ('pending', 'unfinished'):
                terms.append('r.result IS NULL')
            elif status == 'attention':
                terms.append("r.result IN ('parser_failure','technical_failure')")
            elif status in ('valid', 'parser_failure', 'technical_failure'):
                terms.append('r.result=?')
                parameters.append(status)
            else:
                raise ValueError('Unknown run status')
        if search:
            if len(search) > 128:
                raise ValueError('Case search is limited to 128 characters')
            escaped = search.replace('~', '~~').replace('%', '~%').replace('_', '~_').replace('[', '~[')
            terms.append("dc.case_code LIKE ? ESCAPE '~'")
            parameters.append('%' + escaped + '%')
        return ' AND '.join(terms) or '1=1', parameters

    def runs(self, experiment_id=None, model_id=None, prompt_id=None, status=None,
             search='', page=1, page_size=50, repetition=None):
        offset = _page(page, page_size)
        clause, parameters = self._run_filters(experiment_id, model_id, prompt_id, status, search, repetition)
        # Count needs neither predictions nor attempts; page rows never include large evidence/reasons.
        total = self._one('''SELECT COUNT_BIG(*) AS total FROM dbo.experiment_runs r
            JOIN dbo.dataset_cases dc ON dc.id=r.dataset_case_id WHERE ''' + clause, *parameters)['total']
        items = self._rows('SELECT ' + RUN_COLUMNS + ' ' + RUN_FROM + ' WHERE ' + clause + '''
            ORDER BY r.experiment_id DESC,r.run_order OFFSET ? ROWS FETCH NEXT ? ROWS ONLY''',
            *parameters, offset, page_size)
        return dict(items=items, total=total, page=page, page_size=page_size,
                    pages=max(1, (total + page_size - 1) // page_size))

    def filter_options(self, experiment_id=None):
        result = {}
        for key, table, column in [('models', 'models', 'model_id'), ('prompts', 'prompts', 'prompt_id')]:
            clause = '' if experiment_id is None else ' AND r.experiment_id=?'
            parameters = [] if experiment_id is None else [experiment_id]
            result[key] = self._rows(f'''SELECT item.id,item.name FROM dbo.{table} item
                WHERE EXISTS (SELECT 1 FROM dbo.experiment_runs r WHERE r.{column}=item.id{clause})
                ORDER BY item.name,item.id''', *parameters)
        return result

    def run_detail(self, run_id, tab='reasons'):
        if tab not in ('reasons', 'response', 'openapi', 'raw', 'raw-output', 'attempts'):
            raise ValueError('Unknown run detail tab')
        run = self._one('SELECT ' + RUN_COLUMNS + ',r.request_file_id,dc.reference_id,r.run_config_id '
                        + RUN_FROM + ' WHERE r.id=?', run_id)
        references = self._rows('SELECT * FROM dbo.reference_results WHERE id=?', run['reference_id'])
        predictions = self._rows('SELECT * FROM dbo.predictions WHERE run_id=?', run_id)
        attempts = self._rows('SELECT * FROM dbo.run_attempts WHERE run_id=? ORDER BY attempt', run_id)
        evidence = []
        if tab == 'response':
            response = self._one('''SELECT res.status_code,res.content_type,res.body_file_id,res.observed_at
                FROM dbo.test_cases tc JOIN dbo.responses res ON res.id=tc.response_id WHERE tc.id=?''', run['case_id'])
            run['response'] = response
            evidence.append(dict(title='Exact persisted response body', content=_text(self._file(response['body_file_id']))))
        elif tab == 'openapi':
            contract = self._one('''SELECT ac.id,ac.openapi_version,ac.file_id,op.http_method,op.path_template
                FROM dbo.test_cases tc JOIN dbo.api_operations op ON op.id=tc.operation_id
                JOIN dbo.api_contracts ac ON ac.id=op.contract_id WHERE tc.id=?''', run['case_id'])
            run['contract'] = contract
            evidence.append(dict(title='Exact persisted OpenAPI contract', content=_text(self._file(contract['file_id']))))
            if run['request_file_id'] is not None:
                evidence.append(dict(title='Exact persisted request and rendered context', content=_text(self._file(run['request_file_id']))))
        elif tab in ('raw', 'raw-output', 'attempts'):
            for attempt in attempts:
                columns = [('response_file_id', 'Exact provider response')] if tab != 'attempts' else [
                    ('diagnostics_file_id', 'Persisted diagnostics'), ('response_file_id', 'Exact provider response')]
                for column, title in columns:
                    raw = self._file(attempt[column])
                    evidence.append(dict(title=f"Attempt {attempt['attempt']}: {title}",
                                         content=None if raw is None else _text(raw)))
        return dict(run=run, reference=references[0] if references else None,
                    prediction=predictions[0] if predictions else None, attempts=attempts, evidence=evidence)

    def report(self, experiment_id):
        experiment = self._get_experiment(experiment_id)
        if experiment['state'] != 'completed' or not experiment['planned']:
            return None
        records = self._rows('''SELECT TOP (1) er.id,er.file_id,er.input_file_id,f.sha256 AS input_sha256
            FROM dbo.evaluation_reports er JOIN dbo.files f ON f.id=er.input_file_id
            WHERE er.experiment_id=? ORDER BY er.created_at DESC,er.id DESC''', experiment_id)
        if not records:
            return None
        record = records[0]
        try:
            report = json.loads(self._file(record['file_id']))
        except DataUnavailable as exc:
            if isinstance(exc.__cause__, pyodbc.Error):
                raise
            raise ReportUnavailable('The persisted report artifact is missing or failed its integrity check.') from exc
        except (ValueError, TypeError) as exc:
            raise ReportUnavailable('The persisted evaluation report is unreadable.') from exc
        if (not isinstance(report, dict) or report.get('format') != 'comparison-evaluation-v1'
                or report.get('experiment_id') != experiment_id
                or report.get('input_sha256') != record['input_sha256']):
            raise ReportUnavailable('No supported, correctly bound persisted evaluation report is available.')
        return report

    def data_list(self, section, page=1, page_size=50, kind='models'):
        offset = _page(page, page_size)
        if section == 'datasets':
            columns = '''d.id,d.name,d.version,d.purpose,
                (SELECT COUNT_BIG(*) FROM dbo.dataset_cases dc WHERE dc.dataset_id=d.id) AS case_count'''
            source, order = 'FROM dbo.datasets d', 'd.id DESC'
        elif section == 'cases':
            columns = '''tc.id,tc.native_case_id AS [case],api.name AS api,fam.code AS family,
                tc.origin,UPPER(op.http_method)+' '+op.path_template AS operation,
                ref.c1,ref.c2,ref.c3,ref.version,ref.id AS reference_id'''
            source, order = CASE_FROM, 'tc.id'
        elif section == 'references':
            columns = '''ref.id,tc.native_case_id AS [case],tc.id AS case_id,api.name AS api,
                ref.c1,ref.c2,ref.c3,ref.version'''
            source = '''FROM dbo.reference_results ref JOIN dbo.test_cases tc ON tc.id=ref.case_id
                JOIN dbo.api_operations op ON op.id=tc.operation_id
                JOIN dbo.api_contracts ac ON ac.id=op.contract_id JOIN dbo.apis api ON api.id=ac.api_id'''
            order = 'tc.native_case_id,ref.version'
        elif section == 'artifacts':
            if kind not in ARTIFACT_TABLES:
                raise NotFound('Unknown artifact type.')
            table = ARTIFACT_TABLES[kind]
            source, order = f'FROM dbo.{table} a', 'a.id DESC'
            columns = {
                'models': 'a.id,a.name,a.family,a.parameters_b,a.quantization,a.context_length',
                'prompts': 'a.id,a.name,a.version,a.strategy',
                'configs': 'a.id,a.temperature,a.top_p,a.top_k,a.num_ctx,a.num_predict,a.think',
                'contracts': 'a.id,api.name,a.openapi_version,a.imported_at',
                'files': 'a.id,a.name,a.size_bytes',
                'experiments': 'a.id,a.name,a.kind,a.started_at,a.finished_at',
                'reports': 'a.id,e.name,a.created_at',
            }[kind]
            if kind == 'contracts':
                source += ' JOIN dbo.apis api ON api.id=a.api_id'
            elif kind == 'reports':
                source += ' JOIN dbo.experiments e ON e.id=a.experiment_id'
        else:
            raise NotFound('Unknown data section.')
        total = self._one('SELECT COUNT_BIG(*) AS total ' + source)['total']
        items = self._rows('SELECT ' + columns + ' ' + source + ' ORDER BY ' + order
                           + ' OFFSET ? ROWS FETCH NEXT ? ROWS ONLY', offset, page_size)
        return dict(items=items, total=total, page=page, page_size=page_size,
                    pages=max(1, (total + page_size - 1) // page_size))

    def data_detail(self, section, id, kind='models'):
        if section == 'datasets':
            row = self._one('SELECT id,name,version,purpose FROM dbo.datasets WHERE id=?', id)
            count = self._one('SELECT COUNT_BIG(*) AS total FROM dbo.dataset_cases WHERE dataset_id=?', id)['total']
            members = self._rows('''SELECT TOP (200) dc.case_id,dc.case_code,dc.reference_id,dc.position
                FROM dbo.dataset_cases dc WHERE dc.dataset_id=? ORDER BY dc.position''', id)
            metadata = {'Version': row['version'], 'Purpose': row['purpose'], 'Cases': count}
            if count > len(members):
                metadata['Case links shown'] = f'First {len(members)} of {count}; use Cases to inspect the full inventory.'
            return dict(title=row['name'], metadata=metadata,
                        technical={'Dataset ID': id}, evidence=[], relationships=[
                            dict(title=m['case_code'], url=f"/data/cases/{m['case_id']}") for m in members])
        if section == 'cases':
            return self._case_detail(id)
        if section == 'references':
            return self._reference_detail(id)
        if section == 'artifacts' and kind in ARTIFACT_TABLES:
            return self._artifact_detail(id, kind)
        raise NotFound('Unknown data section or artifact type.')

    def _case_detail(self, id):
        row = self._one('''SELECT tc.*,api.name AS api,fam.code AS family,
            UPPER(op.http_method)+' '+op.path_template AS operation,
            ac.id AS contract_id,res.status_code,res.content_type,res.body_file_id,res.observed_at,
            body.sha256 AS body_sha256,source.sha256 AS source_sha256
            FROM dbo.test_cases tc JOIN dbo.api_operations op ON op.id=tc.operation_id
            JOIN dbo.api_contracts ac ON ac.id=op.contract_id JOIN dbo.apis api ON api.id=ac.api_id
            JOIN dbo.case_families fam ON fam.id=tc.family_id JOIN dbo.responses res ON res.id=tc.response_id
            JOIN dbo.files body ON body.id=res.body_file_id JOIN dbo.files source ON source.id=tc.source_file_id
            WHERE tc.id=?''', id)
        references = self._rows('SELECT id,version,c1,c2,c3 FROM dbo.reference_results WHERE case_id=? ORDER BY version', id)
        memberships = self._rows('''SELECT d.id,d.name,d.version,dc.case_code,dc.reference_id
            FROM dbo.dataset_cases dc JOIN dbo.datasets d ON d.id=dc.dataset_id WHERE dc.case_id=? ORDER BY d.id''', id)
        relationships = [dict(title=f"Reference revision {r['version']}", url=f"/data/references/{r['id']}") for r in references]
        relationships += [dict(title=f"{d['name']} {d['version']} · {d['case_code']}", url=f"/data/datasets/{d['id']}") for d in memberships]
        relationships.append(dict(title='OpenAPI contract', url=f"/data/artifacts/{row['contract_id']}?kind=contracts"))
        if row['parent_case_id'] is not None:
            relationships.append(dict(title='Parent case', url=f"/data/cases/{row['parent_case_id']}"))
        bound_ids = {m['reference_id'] for m in memberships}
        bound = next((r for r in references if bound_ids == {r['id']}), None)
        reference_metadata = {'Reference binding': f"Revision {bound['version']}" if bound else
                              'Not available: memberships are absent, unbound, or use different revisions.'}
        reference_metadata.update({c.upper(): bound[c] if bound else None for c in ('c1', 'c2', 'c3')})
        return dict(title=row['native_case_id'], metadata={
            'API': row['api'], 'Family': row['family'], 'Origin': row['origin'], 'Operation': row['operation'],
            **reference_metadata,
            'Description': row['description'], 'Response status': row['status_code'], 'Raw Content-Type': row['content_type'],
            'Observed at': row['observed_at']}, technical={
                'Case ID': id, 'Source namespace': row['source_namespace'], 'Source pointer': row['source_pointer'],
                'Source file ID': row['source_file_id'], 'Body file ID': row['body_file_id'],
                'Source SHA-256': row['source_sha256'], 'Body SHA-256': row['body_sha256'],
                'Parent case ID': row['parent_case_id']}, relationships=relationships, evidence=[
                    dict(title='Exact persisted response body', content=_text(self._file(row['body_file_id']))),
                    dict(title='Persisted source and provenance', content=_json_text(self._source(row['source_file_id'], row['source_pointer'])))])

    def _reference_detail(self, id):
        row = self._one('''SELECT ref.*,tc.native_case_id AS [case],api.name AS api,source.sha256 AS source_sha256
            FROM dbo.reference_results ref JOIN dbo.test_cases tc ON tc.id=ref.case_id
            JOIN dbo.api_operations op ON op.id=tc.operation_id
            JOIN dbo.api_contracts ac ON ac.id=op.contract_id JOIN dbo.apis api ON api.id=ac.api_id
            JOIN dbo.files source ON source.id=ref.source_file_id
            WHERE ref.id=?''', id)
        source = self._source(row['source_file_id'], row['source_pointer'])
        metadata = {'Case': row['case'], 'API': row['api'], 'Version': row['version'],
                    'C1': row['c1'], 'C2': row['c2'], 'C3': row['c3'], 'Notes': row['notes']}
        if isinstance(source, dict):
            for key, title in [('selected_response', 'Selected response branch'), ('selected_media', 'Selected media type'),
                               ('schema_pointer', 'Schema pointer')]:
                metadata[title] = source.get(key)
        return dict(title=f"{row['case']} · reference {row['version']}", metadata=metadata,
                    technical={'Reference ID': id, 'Source file ID': row['source_file_id'], 'Source pointer': row['source_pointer'],
                               'Source SHA-256': row['source_sha256']},
                    evidence=[dict(title='Persisted reference source and diagnostics', content=_json_text(source))],
                    relationships=[dict(title=row['case'], url=f"/data/cases/{row['case_id']}")])

    def _artifact_detail(self, id, kind):
        table = ARTIFACT_TABLES[kind]
        columns = ARTIFACT_COLUMNS[kind]
        row = self._one(f'SELECT {columns} FROM dbo.{table} WHERE id=?', id)
        title = row.get('name') or {'configs': 'Generation configuration', 'contracts': 'OpenAPI contract',
                                   'reports': 'Evaluation report'}.get(kind, 'Artifact')
        technical_keys = {'id', 'digest', 'architecture', 'parent_prompt_id', 'code_version', 'schedule_seed',
                          'sha256', 'baseline_report_id'}
        metadata, technical, evidence, relationships = {}, {}, [], []
        for key, value in row.items():
            label = key.replace('_', ' ').capitalize()
            if key in technical_keys or key.endswith('_id'):
                technical[label] = value
            else:
                metadata[label] = value
        files = []
        if kind == 'files':
            files = [('Exact persisted artifact', id)]
        else:
            files = [(key.replace('_', ' ').capitalize(), value) for key, value in row.items()
                     if key.endswith('_file_id') or key == 'file_id']
        for label, file_id in files:
            if file_id is None:
                evidence.append(dict(title=label, content=None))
                continue
            info = self._one('SELECT name,sha256,size_bytes FROM dbo.files WHERE id=?', file_id)
            technical[label + ' SHA-256'] = info['sha256']
            technical[label + ' bytes'] = info['size_bytes']
            evidence.append(dict(title=label, content=_text(self._file(file_id))))
        if kind == 'experiments':
            relationships.append(dict(title='Experiment overview', url=f"/overview?experiment={id}"))
        if row.get('experiment_id') is not None:
            relationships.append(dict(title='Experiment evaluation', url=f"/evaluation?experiment={row['experiment_id']}"))
        if row.get('dataset_id') is not None:
            relationships.append(dict(title='Dataset', url=f"/data/datasets/{row['dataset_id']}"))
        if kind == 'configs':
            metadata['Database schema version'] = self.schema_version()
        return dict(title=title, metadata=metadata, technical=technical, evidence=evidence, relationships=relationships)
