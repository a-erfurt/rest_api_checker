"""Small transactional write API. No generic public update/delete or provider calls.

Each public write commits atomically. Use transaction() to group multiple writes.
One Repository owns one connection and must not be shared between threads.
"""
from contextlib import contextmanager
from decimal import Decimal
from functools import wraps
from hashlib import sha256
import json
import re

from .database import (IntegrityViolation, decimal_value, integer, json_bytes, lock,
                       pointer, require, text_bound, timestamp, utc_now)
from .migrate import verify

TABLES = ('files apis api_contracts api_operations case_families responses test_cases '
          'reference_results datasets dataset_cases models prompts run_configs experiments '
          'experiment_runs run_attempts predictions evaluation_reports').split()
ORIGINS = {'NATURAL': 'natural_observation', 'SYNTHETIC_CONFORMANT': 'synthetic_conformant_control',
           'SYNTHETIC_INCONSISTENT': 'synthetic_inconsistency'}
VERDICTS = {'PASS', 'FAIL', 'NOT_APPLICABLE'}
REFERENCE_VECTORS = {('PASS','PASS','PASS'), ('PASS','PASS','FAIL'),
                     ('PASS','FAIL','NOT_APPLICABLE'), ('FAIL','NOT_APPLICABLE','NOT_APPLICABLE')}
D07 = dict(temperature=Decimal('0.200'), top_p=Decimal('0.900'), top_k=40,
           min_p=Decimal('0.000'), repeat_penalty=Decimal('1.000'), repeat_last_n=64,
           draft_num_predict=0, num_ctx=32768, num_predict=512, stream=False, timeout_seconds=300)


def atomic(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with self.transaction():
            return method(self, *args, **kwargs)
    return wrapped


class Repository:
    def __init__(self, connection):
        require(not connection.autocommit, 'Repository requires a transactional connection')
        self.cn = connection
        verify(connection)  # Check only, never migration.
        self._depth = 0
        self._rollback_only = False
        self._columns = {}
        for r in connection.execute('''SELECT t.name,c.name,ty.name,c.max_length,c.precision,c.scale,c.is_nullable
                FROM sys.tables t JOIN sys.columns c ON c.object_id=t.object_id
                JOIN sys.types ty ON ty.user_type_id=c.user_type_id WHERE SCHEMA_NAME(t.schema_id)='dbo' '''):
            self._columns.setdefault(r[0], {})[r[1]] = tuple(r[2:])
        connection.commit()

    @contextmanager
    def transaction(self):
        outer = self._depth == 0
        if outer:
            self._rollback_only = False
        self._depth += 1
        try:
            yield self
            require(not self._rollback_only, 'Nested write failed; transaction cannot commit')
            if outer:
                self.cn.commit()
        except BaseException:
            self._rollback_only = True
            if outer:
                self.cn.rollback()
            raise
        finally:
            self._depth -= 1

    def _validate(self, table, values):
        require(table in TABLES, 'Unknown table')
        for column, value in values.items():
            require(column in self._columns[table] and column not in ('id','size_bytes'), 'Unknown/derived column')
            kind, length, precision, scale, nullable = self._columns[table][column]
            if value is None:
                require(nullable, f'{table}.{column} cannot be missing')
            elif kind in ('nvarchar','varchar','char'):
                text_bound(value, None if length == -1 else length//(2 if kind=='nvarchar' else 1),
                           ascii_only=kind!='nvarchar')
            elif kind in ('bigint','int','smallint'):
                integer(value, {'bigint':64,'int':32,'smallint':16}[kind])
            elif kind == 'decimal':
                decimal_value(value, precision, scale)
            elif kind == 'bit':
                require(type(value) is bool, 'BIT requires bool, not truthiness')
            elif kind == 'datetimeoffset':
                timestamp(value)
            elif kind == 'varbinary':
                require(type(value) is bytes and len(value) <= 2**31-1, 'Exact bytes required')

    def _insert(self, table, **values):
        self._validate(table, values)
        columns = ','.join(values)
        placeholders = ','.join('CONVERT(datetimeoffset(7),?,127)' if self._columns[table][k][0]=='datetimeoffset'
                                else '?' for k in values)
        return self.cn.execute(f'INSERT dbo.{table} ({columns}) OUTPUT INSERTED.id VALUES ({placeholders})',
                               *values.values()).fetchval()

    def _row(self, table, row_id):
        require(table in TABLES, 'Unknown table')
        cur = self.cn.execute(f'SELECT * FROM dbo.{table} WHERE id=?', integer(row_id))
        row = cur.fetchone()
        require(row is not None, f'Missing {table} row')
        return dict(zip([d[0] for d in cur.description], row))

    def _same(self, table, keys, values):
        self._validate(table, values)
        for key in keys:
            if isinstance(values[key], str):
                text_bound(values[key], identity=True)
        lock(self.cn, 'identity:' + table + ':' + sha256(json_bytes([values[k] for k in keys])).hexdigest())
        clause = ' AND '.join(f'{k}=?' for k in keys)
        row_id = self.cn.execute(f'SELECT id FROM dbo.{table} WHERE {clause}', *[values[k] for k in keys]).fetchval()
        if row_id is not None:
            stored = self._row(table, row_id)
            require(all(stored[k] == v for k,v in values.items()), f'Changed evidence under {table} identity')
            return row_id
        return self._insert(table, **values)

    @atomic
    def archive(self, name, content):
        text_bound(name, 512, identity=True)
        require(type(content) is bytes, 'Archive original bytes, never decoded text')
        digest = sha256(content).hexdigest()
        lock(self.cn, 'file:' + digest)
        row = self.cn.execute('SELECT id,size_bytes,content FROM dbo.files WHERE sha256=?', digest).fetchone()
        if row:
            require(row[1] == len(content) and bytes(row[2]) == content, 'SHA-256 collision/content corruption')
            return row[0]
        return self._insert('files', name=name, content=content, sha256=digest)

    def file(self, file_id):
        row = self._row('files', file_id)
        raw = bytes(row['content'])
        require(len(raw)==row['size_bytes'] and sha256(raw).hexdigest()==row['sha256'], 'Archived byte integrity failure')
        return raw

    def source(self, file_id, source_pointer):
        text_bound(source_pointer, 512, identity=True, empty=True)
        return pointer(json.loads(self.file(file_id)), source_pointer)

    @atomic
    def api(self, name, description=None):
        return self._same('apis', ('name',), dict(name=name, description=description))

    @atomic
    def contract(self, api_id, file_id, openapi_version):
        require(json.loads(self.file(file_id)).get('openapi') == openapi_version, 'Contract version/source mismatch')
        lock(self.cn, f'contract:{api_id}:{file_id}')
        old = self.cn.execute('SELECT id,openapi_version FROM dbo.api_contracts WHERE api_id=? AND file_id=?', api_id,file_id).fetchone()
        if old:
            require(old[1] == openapi_version, 'Contract version changed')
            return old[0]
        return self._insert('api_contracts', api_id=api_id, file_id=file_id, openapi_version=openapi_version, imported_at=utc_now())

    @atomic
    def operation(self, contract_id, http_method, path_template):
        contract = self._row('api_contracts', contract_id)
        raw = json.loads(self.file(contract['file_id']))
        require(http_method in raw.get('paths',{}).get(path_template,{}), 'Operation absent from exact contract')
        return self._same('api_operations', ('contract_id','http_method','path_template'),
                          dict(contract_id=contract_id,http_method=http_method,path_template=path_template))

    @atomic
    def family(self, api_id, code):
        return self._same('case_families', ('api_id','code'), dict(api_id=api_id,code=code))

    @atomic
    def response(self, status_code, content_type, body_file_id, observed_at=None):
        # Intentionally always a new observation, even when bytes/envelope match.
        return self._insert('responses', status_code=status_code,content_type=content_type,
                            body_file_id=body_file_id,observed_at=observed_at)

    @atomic
    def case(self, *, source_namespace, native_case_id, operation_id, response_id, family_id,
             origin, parent_case_id, source_file_id, source_pointer, description=None):
        values = dict(source_namespace=source_namespace,native_case_id=native_case_id,operation_id=operation_id,
                      response_id=response_id,family_id=family_id,origin=origin,parent_case_id=parent_case_id,
                      source_file_id=source_file_id,source_pointer=source_pointer,description=description)
        record = self.source(source_file_id, source_pointer)
        require(record['case_id'] == native_case_id, 'Source pointer resolves to another case')
        require(ORIGINS.get(record['origin'],record['origin']) == origin, 'Source origin mismatch')
        operation = self._row('api_operations',operation_id)
        contract = self._row('api_contracts',operation['contract_id'])
        family = self._row('case_families',family_id)
        require(contract['api_id']==family['api_id'], 'Family/API mismatch')
        require(record['root_family']==family['code'] and record['api']==self._row('apis',family['api_id'])['name'],
                'Native family/API mismatch')
        require(record['operation']=={'method':operation['http_method'],'path':operation['path_template']},
                'Source operation mismatch')
        require(record['contract_sha256']==sha256(self.file(contract['file_id'])).hexdigest(), 'Source contract mismatch')
        response = self._row('responses',response_id)
        require(record['status']==response['status_code'] and record['content_type']==response['content_type']
                and record['body']['sha256']==sha256(self.file(response['body_file_id'])).hexdigest(), 'Source response mismatch')
        if parent_case_id is not None:
            parent = self._row('test_cases',parent_case_id)
            require(parent['family_id']==family_id and parent['operation_id']==operation_id
                    and parent['source_namespace']==source_namespace, 'Parent lineage mismatch')
            require(record['immediate_parent']==parent['native_case_id'] and origin!='natural_observation', 'Parent source mismatch')
        else:
            require(record['immediate_parent'] is None, 'Missing parent')
        # Existing rows are immutable; insertion can only point to earlier ancestors, so no cycles.
        return self._same('test_cases', ('source_namespace','native_case_id'), values)

    @atomic
    def reference(self, case_id, version, source_file_id, source_pointer, notes=None):
        record = self.source(source_file_id,source_pointer)
        require(set(('c1','c2','c3','vector','overall','selected_response','selected_media','schema_pointer','diagnostics')) <= record.keys(),
                'Incomplete Oracle source record')
        vector = tuple(record[c] for c in ('c1','c2','c3'))
        require(vector in REFERENCE_VECTORS and list(vector)==record['vector'], 'Unsupported/incomplete reference vector')
        require(record['overall']==('INCONSISTENT' if 'FAIL' in vector else 'CONSISTENT'), 'Reference overall mismatch')
        require(all(record[key] is None or isinstance(record[key],str)
                    for key in ('selected_response','selected_media','schema_pointer'))
                and isinstance(record['diagnostics'],list), 'Malformed Oracle source record')
        for diagnostic in record['diagnostics']:
            require(isinstance(diagnostic,dict) and set(diagnostic)=={'code','instance_pointer','schema_path','keyword'}
                    and all(isinstance(value,str) for value in diagnostic.values()), 'Malformed Oracle diagnostic')
        # The container must identify the owning case alongside its oracle object.
        parent_path = source_pointer.rsplit('/',1)[0] if '/' in source_pointer else ''
        owner = self.source(source_file_id,parent_path)
        case = self._row('test_cases',case_id)
        require(isinstance(owner,dict) and owner.get('case_id')==case['native_case_id'],
                'Reference pointer/case mismatch')
        original = self.source(case['source_file_id'],case['source_pointer'])
        unchanged = ('case_id','api','operation','root_family','origin','immediate_parent',
                     'contract_sha256','status','content_type')
        require(all(owner.get(key)==original[key] for key in unchanged)
                and owner.get('body',{}).get('sha256')==original['body']['sha256'],
                'Reference revision changes case inputs or lineage')
        lock(self.cn, f'reference:{case_id}')
        previous = self.cn.execute('SELECT id,version FROM dbo.reference_results WHERE case_id=? AND source_file_id=? AND source_pointer=?',
                                   case_id,source_file_id,source_pointer).fetchone()
        if previous:
            require(previous[1]==version, 'Reference source already has a different explicit revision')
        return self._same('reference_results', ('case_id','version'), dict(case_id=case_id,version=version,
            c1=vector[0],c2=vector[1],c3=vector[2],source_file_id=source_file_id,source_pointer=source_pointer,notes=notes))

    @atomic
    def dataset(self, name, version, purpose):
        return self._same('datasets', ('name','version'), dict(name=name,version=version,purpose=purpose))

    @atomic
    def membership(self, dataset_id, case_id, reference_id, case_code, position):
        lock(self.cn, f'dataset:{dataset_id}')
        values = dict(dataset_id=dataset_id,case_id=case_id,reference_id=reference_id,case_code=case_code,position=position)
        old = self.cn.execute('SELECT id FROM dbo.dataset_cases WHERE dataset_id=? AND case_id=?',dataset_id,case_id).fetchval()
        if old is None:
            require(not self.cn.execute('SELECT 1 FROM dbo.experiments WHERE dataset_id=?',dataset_id).fetchone(), 'Used dataset is immutable')
        return self._same('dataset_cases', ('dataset_id','case_id'), values)

    @atomic
    def bind_reference(self, membership_id, reference_id):
        row = self._row('dataset_cases',membership_id)
        lock(self.cn, f'dataset:{row["dataset_id"]}')
        row = self._row('dataset_cases',membership_id)
        require(not self.cn.execute('SELECT 1 FROM dbo.experiments WHERE dataset_id=?',row['dataset_id']).fetchone(), 'Used dataset is immutable')
        require(row['reference_id'] is None or row['reference_id']==reference_id, 'Existing binding is immutable')
        self.cn.execute('UPDATE dbo.dataset_cases SET reference_id=? WHERE id=? AND reference_id IS NULL',reference_id,membership_id)

    @atomic
    def model(self, *, name, family, parameters_b, quantization, context_length, digest, architecture, metadata_file_id=None):
        require(re.fullmatch(r'(?:sha256:)?[0-9a-f]{64}',digest) is not None, 'Full model digest required')
        return self._same('models', ('name','digest'), dict(name=name,family=family,parameters_b=parameters_b,
            quantization=quantization,context_length=context_length,digest=digest,architecture=architecture,metadata_file_id=metadata_file_id))

    @atomic
    def prompt(self, name, version, strategy, file_id, parent_prompt_id=None):
        self.file(file_id).decode('utf-8')
        return self._same('prompts', ('name','version'), dict(name=name,version=version,strategy=strategy,file_id=file_id,parent_prompt_id=parent_prompt_id))

    @atomic
    def configuration(self, *, think, **settings):
        require(set(settings)==set(D07), 'Explicit complete configuration required')
        return self._insert('run_configs',think=think,**settings)

    def require_d07(self, config_id, model_name):
        row = self._row('run_configs',config_id)
        require(all(row[k]==v for k,v in D07.items()), 'D07 configuration mismatch')
        require(model_name in ('qwen3.6:27b','gemma3:27b','mistral-small3.2:24b'), 'Unapproved model roster')
        require(row['think'] is (False if model_name=='qwen3.6:27b' else None), 'False/omitted think mismatch')

    @atomic
    def verify_comparison_bindings(self, dataset_id, memberships, prompts, models, configs):
        """Validate schedule adapters against immutable relational/source identities."""
        from .importer import PROMPT_HASHES
        for code, row_id in memberships.items():
            row = self._row('dataset_cases', row_id)
            require(row['dataset_id']==dataset_id and row['case_code']==code,
                    'Schedule membership identity mismatch')
        for name, row_id in prompts.items():
            row = self._row('prompts', row_id)
            require(row['name']==name and sha256(self.file(row['file_id'])).hexdigest()==PROMPT_HASHES[name],
                    'Schedule prompt identity mismatch')
        for name, row_id in models.items():
            require(self._row('models', row_id)['name']==name, 'Schedule model identity mismatch')
            self.require_d07(configs[name], name)

    @atomic
    def execution_inputs(self, run_id):
        """Read one immutable run binding, committing the read before any network I/O.

        Evidence is an explicit projection; reference/family/case records are
        never handed to the renderer. Sidecar/setup remain separate.
        """
        from ..experiment.renderer import Evidence
        run = self._row('experiment_runs', run_id)
        experiment = self._row('experiments', run['experiment_id'])
        setup_raw = self.file(experiment['setup_file_id'])
        setup = json.loads(setup_raw)
        require({k:run[k] for k in ('dataset_case_id','model_id','prompt_id','run_config_id',
                                    'repetition','seed','run_order')} in setup['schedule'],
                'Run differs from frozen schedule')
        membership = self._row('dataset_cases',run['dataset_case_id'])
        case = self._row('test_cases',membership['case_id'])
        operation = self._row('api_operations',case['operation_id'])
        contract = self._row('api_contracts',operation['contract_id'])
        response = self._row('responses',case['response_id'])
        prompt = self._row('prompts',run['prompt_id'])
        model = self._row('models',run['model_id'])
        self.require_d07(run['run_config_id'],model['name'])
        self.verify_closure(setup['files'])
        return dict(run=run, setup=setup, setup_sha256=sha256(setup_raw).hexdigest(),
            evidence=Evidence(self.file(contract['file_id']),operation['http_method'],
                operation['path_template'],response['status_code'],response['content_type'],
                self.file(response['body_file_id'])),
            contract_identity=f'files:{contract["file_id"]}', body_identity=f'files:{response["body_file_id"]}',
            prompt_name=prompt['name'],prompt=self.file(prompt['file_id']),model=model)

    @contextmanager
    def dispatch_owner(self):
        """Single session-owned database claim; never a transaction spanning HTTP.

        A disconnected owner cannot authorize takeover of an existing reserved
        slot. reserve() still refuses it and requires explicit reconciliation.
        """
        require(self._depth==0, 'Dispatch cannot run inside a caller transaction')
        result = self.cn.execute("""DECLARE @r INT;
            EXEC @r=sys.sp_getapplock @Resource='rest_api_checker:dispatch',
              @LockMode='Exclusive',@LockOwner='Session',@LockTimeout=0;
            SELECT @r;""").fetchval()
        self.cn.commit()
        require(result>=0, 'Another orchestrator owns dispatch')
        try:
            yield
        finally:
            self.cn.execute("""EXEC sys.sp_releaseapplock @Resource='rest_api_checker:dispatch',
                            @LockOwner='Session';""")
            self.cn.commit()

    @atomic
    def attempt_state(self, attempt_id):
        return self._row('run_attempts', attempt_id)

    @contextmanager
    def provider_io(self, attempt_id):
        """Expose one start callback and suspend ODBC manual transactions for I/O.

        The SQL Server ODBC manual-commit mode can retain an initialized server
        transaction after SQLCommit. Explicit autocommit during the network-only
        window also makes the absence of a server transaction externally testable.
        The session dispatch claim survives; no application writes occur here.
        """
        require(self._depth==0 and not self.cn.autocommit, 'Invalid provider I/O boundary')
        started = False
        def observe(at):
            nonlocal started
            require(not started, 'Provider start already observed')
            self.observe_start(attempt_id, at)
            self.cn.autocommit = True
            started = True
        try:
            yield observe
            require(started, 'Provider did not observe dispatch start')
        finally:
            self.cn.autocommit = False

    @atomic
    def plan_experiment(self, *, name, kind, dataset_id, schedule_seed, setup, schedule, notes=None):
        """Persist a caller-supplied frozen schedule, not generate one or authorize dispatch.

        Full Gate B/provider/renderer validation is a later boundary. This method
        verifies relational/source closure and the explicit supplied schedule set.
        """
        lock(self.cn, f'dataset:{dataset_id}')
        dataset = self._row('datasets',dataset_id)
        require(kind in ('comparison','sensitivity') and dataset['purpose']=='development',
                'Final evaluation admission is deferred; development phase mismatch')
        require(schedule and setup['schedule']==schedule and setup['dataset_id']==dataset_id
                and setup['schedule_seed']==schedule_seed, 'Frozen schedule mismatch')
        require(re.fullmatch('[0-9a-f]{64}',setup.get('parser_sha256','')) is not None, 'Explicit parser identity required')
        self.verify_closure(setup['files'])
        for run in schedule:
            require(set(run)=={'dataset_case_id','model_id','prompt_id','run_config_id','repetition','seed','run_order'}, 'Unexpected planned-run fields')
            membership = self._row('dataset_cases',run['dataset_case_id'])
            require(membership['dataset_id']==dataset_id and membership['reference_id'] is not None, 'Incomplete/wrong dataset reference')
            ref = self._row('reference_results',membership['reference_id'])
            require(ref['case_id']==membership['case_id'], 'Reference/case mismatch')
            self.source(ref['source_file_id'],ref['source_pointer'])
            case = self._row('test_cases',membership['case_id'])
            self.case(**{k:v for k,v in case.items() if k!='id'})
            self.reference(ref['case_id'],ref['version'],ref['source_file_id'],ref['source_pointer'],ref['notes'])
            require(100 <= self._row('responses',case['response_id'])['status_code'] <= 599, 'Ineligible response status')
        from .inspection import bindings
        bound = bindings(self, dataset_id, schedule)
        require('bindings' not in setup or setup['bindings'] == bound, 'Supplied setup bindings drift')
        setup = {**setup, 'bindings': bound}
        setup_file = self.archive('experiment-setup.json',json_bytes(setup))
        experiment_id = self._insert('experiments',name=name,kind=kind,dataset_id=dataset_id,
            setup_file_id=setup_file,schedule_seed=schedule_seed,started_at=None,finished_at=None,notes=notes)
        ids = [self._insert('experiment_runs',experiment_id=experiment_id,dataset_id=dataset_id,**run) for run in schedule]
        return experiment_id, ids

    def verify_closure(self, files):
        require(isinstance(files,list) and files, 'Source closure required')
        for item in files:
            raw = self.file(item['file_id'])
            require(sha256(raw).hexdigest()==item['sha256'], 'Source closure hash mismatch')
            if 'pointer' in item:
                pointer(json.loads(raw),item['pointer'])

    @atomic
    def reserve(self, run_id, request, *, attempt, prepared_at=None):
        require(attempt in (1,2), 'Only two attempt slots exist')
        lock(self.cn, f'run:{run_id}')
        run = self._row('experiment_runs',run_id)
        require(run['result'] is None, 'Completed outcome is immutable')
        membership = self._row('dataset_cases',run['dataset_case_id'])
        require(membership['reference_id'] is not None, 'Incomplete reference cannot be reserved')
        require(not self.cn.execute('SELECT 1 FROM dbo.run_attempts WHERE run_id=? AND attempt=?',run_id,attempt).fetchone(),
                'Slot already reserved; reconcile, never dispatch again')
        if attempt == 2:
            first = self.cn.execute('SELECT id,result,diagnostics_file_id FROM dbo.run_attempts WHERE run_id=? AND attempt=1',run_id).fetchone()
            require(first and first[1]=='technical_failure', 'Retry requires a recorded technical failure')
            diagnostic = self._diagnostic_root(first[2])
            require(diagnostic.get('retry_eligible') is True, 'Failure attribution does not qualify for retry')
        file_id = self.archive('frozen-request.bin',request)
        require(run['request_file_id'] in (None,file_id), 'Retry/frozen request mismatch')
        self.cn.execute('UPDATE dbo.experiment_runs SET request_file_id=? WHERE id=? AND request_file_id IS NULL',file_id,run_id)
        return self._insert('run_attempts',run_id=run_id,attempt=attempt,request_file_id=file_id,prepared_at=prepared_at or utc_now())

    @atomic
    def observe_start(self, attempt_id, started_at):
        """Record an observed dispatch time only; reservation never implies dispatch."""
        timestamp(started_at)
        require(started_at is not None, 'Observed timestamp required')
        attempt = self._row('run_attempts',attempt_id)
        lock(self.cn,f'run:{attempt["run_id"]}')
        attempt = self._row('run_attempts',attempt_id)
        require(attempt['result'] is None and attempt['started_at'] is None, 'Start already recorded or terminal')
        self.cn.execute('UPDATE dbo.run_attempts SET started_at=CONVERT(datetimeoffset(7),?,127) WHERE id=?',started_at,attempt_id)
        self.cn.execute('UPDATE dbo.experiment_runs SET started_at=CONVERT(datetimeoffset(7),?,127) WHERE id=? AND started_at IS NULL',started_at,attempt['run_id'])
        run = self._row('experiment_runs',attempt['run_id'])
        self.cn.execute('UPDATE dbo.experiments SET started_at=CONVERT(datetimeoffset(7),?,127) WHERE id=? AND started_at IS NULL',started_at,run['experiment_id'])

    def _diagnostic_root(self, file_id):
        seen = set()
        while True:
            if file_id is None:
                return {}
            require(file_id not in seen, 'Diagnostic cycle')
            seen.add(file_id)
            value = json.loads(self.file(file_id))
            if value.get('format') != 'diagnostic-successor-v1':
                return value
            previous = value['previous_file_id']
            require(sha256(self.file(previous)).hexdigest()==value['previous_sha256'], 'Diagnostic predecessor mismatch')
            file_id = previous

    @atomic
    def finalize(self, attempt_id, *, result, response, diagnostics, prediction=None,
                 http_status=None, done_reason=None, error_kind=None, error_message=None,
                 duration_ms=None, prompt_tokens=None, output_tokens=None, finished_at):
        attempt = self._row('run_attempts',attempt_id)
        lock(self.cn,f'run:{attempt["run_id"]}')
        attempt = self._row('run_attempts',attempt_id)
        run = self._row('experiment_runs',attempt['run_id'])
        setup = json.loads(self.file(self._row('experiments',run['experiment_id'])['setup_file_id']))
        require(result in ('valid','parser_failure','technical_failure'), 'Illegal outcome')
        require(finished_at is not None, 'Observed finalization time required')
        require(diagnostics.get('parser_sha256')==setup['parser_sha256'], 'Parser identity changed/missing')
        require(diagnostics.get('run_id')==run['id'] and diagnostics.get('attempt_id')==attempt_id
                and diagnostics.get('request_sha256')==sha256(self.file(attempt['request_file_id'])).hexdigest(), 'Diagnostic identity mismatch')
        require(type(diagnostics.get('retry_eligible')) is bool, 'Explicit retry attribution required')
        require(not diagnostics['retry_eligible'] or (result=='technical_failure' and attempt['attempt']==1), 'Invalid retry entitlement')
        require((result=='valid') == (prediction is not None), 'Prediction/outcome mismatch')
        if prediction is not None:
            require(response is not None, 'Valid output requires captured response bytes')
            require(set(prediction)=={'c1','c1_reason','c2','c2_reason','c3','c3_reason'}, 'Complete prediction required')
            for key in ('c1','c2','c3'):
                require(prediction[key] in VERDICTS and isinstance(prediction[key+'_reason'],str)
                        and bool(prediction[key+'_reason'].strip()), 'Illegal parsed prediction')
        diagnostics = dict(diagnostics)
        # Preserve pending recovery evidence when settling, and reconstruct the
        # same augmented record on a lost-acknowledgement replay.
        prior = attempt['diagnostics_file_id']
        if attempt['result'] is not None:
            predecessor = self._diagnostic_root(prior).get('preceding_evidence')
        elif prior is not None:
            predecessor = dict(file_id=prior,sha256=sha256(self.file(prior)).hexdigest())
        else:
            predecessor = None
        require('preceding_evidence' not in diagnostics, 'Predecessor links are repository-owned')
        if predecessor is not None:
            diagnostics['preceding_evidence'] = predecessor
        response_id = None if response is None else self.archive('provider-response.bin',response)
        diagnostics_id = self.archive('attempt-diagnostics.json',json_bytes(diagnostics))
        values = dict(response_file_id=response_id,diagnostics_file_id=diagnostics_id,http_status=http_status,
            done_reason=done_reason,error_kind=error_kind,error_message=error_message,result=result,
            duration_ms=duration_ms,prompt_tokens=prompt_tokens,output_tokens=output_tokens,finished_at=finished_at)
        self._validate('run_attempts',values)
        if attempt['result'] is not None:
            # SQL normalizes fractional padding; compare timestamps in SQL, never truncate precision.
            equal_time = self.cn.execute('SELECT 1 FROM dbo.run_attempts WHERE id=? AND finished_at=CONVERT(datetimeoffset(7),?,127)',attempt_id,finished_at).fetchone()
            require(equal_time and all(attempt[k]==v for k,v in values.items() if k not in ('finished_at','diagnostics_file_id'))
                    and self._diagnostic_root(attempt['diagnostics_file_id'])==diagnostics, 'Conflicting settled outcome; retain spool and reconcile')
            stored = self.cn.execute('SELECT c1,c1_reason,c2,c2_reason,c3,c3_reason FROM dbo.predictions WHERE attempt_id=?',attempt_id).fetchone()
            require((stored is None and prediction is None) or (stored is not None and prediction is not None and
                    tuple(stored)==tuple(prediction[k] for k in ('c1','c1_reason','c2','c2_reason','c3','c3_reason'))), 'Conflicting prediction')
            return False
        require(run['result'] is None, 'Logical run already completed')
        require(not self.cn.execute('SELECT 1 FROM dbo.run_attempts WHERE run_id=? AND attempt>?',run['id'],attempt['attempt']).fetchone(), 'Later attempt exists')
        assignments = ','.join(k+'='+('CONVERT(datetimeoffset(7),?,127)' if k=='finished_at' else '?') for k in values)
        self.cn.execute(f'UPDATE dbo.run_attempts SET {assignments} WHERE id=?',*values.values(),attempt_id)
        if prediction is not None:
            self._insert('predictions',run_id=run['id'],attempt_id=attempt_id,**prediction)
        if not (result=='technical_failure' and attempt['attempt']==1):
            self.cn.execute('UPDATE dbo.experiment_runs SET result=?,finished_at=CONVERT(datetimeoffset(7),?,127) WHERE id=?',result,finished_at,run['id'])
        # Non-qualifying first technical failure remains pending for explicit reconciliation.
        return True

    @atomic
    def append_diagnostics(self, attempt_id, *, expected_file_id, evidence):
        attempt = self._row('run_attempts',attempt_id)
        lock(self.cn,f'run:{attempt["run_id"]}')
        attempt = self._row('run_attempts',attempt_id)
        require(attempt['diagnostics_file_id']==expected_file_id, 'Diagnostic compare-and-swap conflict; rebuild from latest')
        self.verify_closure(evidence['files'])
        previous_hash = None if expected_file_id is None else sha256(self.file(expected_file_id)).hexdigest()
        value = dict(format='diagnostic-successor-v1',attempt_id=attempt_id,run_id=attempt['run_id'],
                     previous_file_id=expected_file_id,previous_sha256=previous_hash,evidence=evidence)
        file_id = self.archive('diagnostic-successor.json',json_bytes(value))
        self.cn.execute('UPDATE dbo.run_attempts SET diagnostics_file_id=? WHERE id=?',file_id,attempt_id)
        return file_id

    @atomic
    def complete_experiment(self, experiment_id, *, finished_at):
        lock(self.cn,f'experiment:{experiment_id}')
        require(finished_at is not None, 'Observed completion time required')
        experiment = self._row('experiments',experiment_id)
        setup = json.loads(self.file(experiment['setup_file_id']))
        cur = self.cn.execute('SELECT dataset_case_id,model_id,prompt_id,run_config_id,repetition,seed,run_order,result FROM dbo.experiment_runs WHERE experiment_id=? ORDER BY run_order',experiment_id)
        rows = cur.fetchall()
        keys = [d[0] for d in cur.description][:-1]
        require([dict(zip(keys,r[:-1])) for r in rows]==sorted(setup['schedule'],key=lambda r:r['run_order'])
                and all(r[-1] is not None for r in rows), 'Incomplete/drifted schedule')
        require(experiment['finished_at'] is None, 'Experiment already finished')
        self.cn.execute('UPDATE dbo.experiments SET finished_at=CONVERT(datetimeoffset(7),?,127) WHERE id=?',finished_at,experiment_id)

    @atomic
    def report(self, *, experiment_id, input_file_id, file_id, code_version, baseline_report_id=None):
        """Low-level metadata insert; comparison publication uses evaluation.create_report."""
        require(self._row('experiments',experiment_id)['finished_at'] is not None, 'Unfinished experiment')
        inputs = json.loads(self.file(input_file_id))
        report = json.loads(self.file(file_id))
        require(inputs['experiment_id']==experiment_id and report['input_sha256']==sha256(self.file(input_file_id)).hexdigest(), 'Report/input mismatch')
        self.verify_closure(inputs['files'])
        for binding in inputs['references']:
            run = self._row('experiment_runs',binding['run_id'])
            case_id = self._row('dataset_cases',run['dataset_case_id'])['case_id']
            require(run['experiment_id']==experiment_id and self._row('reference_results',binding['reference_id'])['case_id']==case_id, 'Report reference/case mismatch')
        return self._insert('evaluation_reports',experiment_id=experiment_id,input_file_id=input_file_id,file_id=file_id,
            code_version=code_version,baseline_report_id=baseline_report_id,created_at=utc_now())
