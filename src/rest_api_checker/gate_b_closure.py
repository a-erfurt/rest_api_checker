"""Validate separately captured technical closure; never author-accept Gate B."""
import json
from pathlib import Path

from . import runtime_evidence
from .experiment.encoding import digest
from .persistence.database import require

DIRECTORY = 'docs/gate_b_closure_2026-09-26'


def inspect(root, research):
    folder=root/DIRECTORY
    if not (folder/'bundle.json').exists():
        return {}
    bundle=json.loads((folder/'bundle.json').read_bytes())
    require(bundle['format']=='gate-b-technical-closure-v1' and bundle['author_acceptance'] is False,
            'Invalid technical closure scope')
    require({'research:03_research_design/prompt_development_protocol_v1.md',
        'implementation:src/rest_api_checker/experiment/provider.py',
        'implementation:src/rest_api_checker/experiment/orchestration.py',
        'implementation:src/rest_api_checker/persistence/repository.py',
        'implementation:tests/persistence/test_application_security.py'} <= set(bundle['sources']),
        'Missing technical qualification source bindings')
    for key,sha in bundle['sources'].items():
        namespace,relative=key.split(':',1)
        require(namespace in ('implementation','research') and not Path(relative).is_absolute()
                and '..' not in Path(relative).parts,'Unsafe closure source')
        base=root if namespace=='implementation' else research
        require(digest((base/relative).read_bytes())==sha,'Technical closure source drift: '+key)
    def read(name):
        require(name in bundle['files'] and Path(name).name==name,'Unbound closure evidence')
        raw=(folder/name).read_bytes()
        require(digest(raw)==bundle['files'][name],'Technical closure evidence drift: '+name)
        return json.loads(raw)
    for name,sha in bundle['files'].items():
        require(Path(name).name==name and digest((folder/name).read_bytes())==sha,'Closure evidence drift: '+name)
    # The prior capture remains immutable. Its entire native-runtime/source closure
    # must still pass, including the measured request/seed/template/token evidence.
    runtime=runtime_evidence.inspect(root,research)
    require(all(runtime[n]['status']=='PASS' for n in
        ('Full model identities','Template and effective options','Context fit')),'Prior runtime evidence invalid')
    failure=json.loads((root/runtime_evidence.DIRECTORY/'failures.json').read_bytes())
    require(failure['scope']=='FABRICATED_RUNTIME_QUALIFICATION' and failure['sql_writes']==0,
            'Failure capture scope')
    measured={r['name']:r for r in failure['results']}
    for name,code in (('transport','transport'),('timeout','timeout'),('server','HTTP_SERVER_FAILURE')):
        row=measured[name]
        require(row['provider_kind']=='TECHNICAL_FAILURE' and row['provider_code']==code
            and row['outcomes']==[dict(attempt=1,result='technical_failure',retry_eligible=True),
                                  dict(attempt=2,result='technical_failure',retry_eligible=False)]
            and set(row['holds'])=={'ambiguous','systematic'},'Technical failure/retry/hold evidence')
    for name,result in (('parser','parser_failure'),('valid','valid')):
        require(measured[name]['provider_kind']=='FINAL'
                and all(r['result']==result and r['retry_eligible'] is False for r in measured[name]['outcomes']),
                'Completed answer attribution evidence')
    rejected=measured['invalid_option']
    require(rejected['evidence_scope']=='actual_ollama_configuration_rejection_no_generation'
            and rejected['http_status']==500 and rejected['provider_kind']=='TECHNICAL_FAILURE'
            and rejected['attribution']=='systematic deliberately invalid configuration; no retry',
            'Real runtime systematic rejection evidence')
    tests=read('test_results.json')
    require(tests['sql_enabled'] and tests['application_login_enabled'] and tests['backup_restore_enabled'],
            'SQL/application/backup qualification absent')
    full=tests['full']
    require(full['tests']>0 and full['failures']==full['errors']==full['skipped']==0,'Incomplete qualification tests')
    for group in ('tests.persistence.test_application_security','tests.persistence.test_experiment',
                  'tests.experiment.test_boundaries','tests.test_oracle_qualification'):
        require(full['test_counts_by_class'].get(group,0)>0,'Required qualification group absent: '+group)
    decision=read('failure_decision.json')
    require(decision['status']=='AUTHOR DECISION REQUIRED' and decision['crash_oom_observed'] is False
            and decision['protocol_requires_induced_crash_oom'] is False
            and decision['ambiguous_failure_policy']=='RETAIN_AND_BLOCK_ADJUDICATION'
            and decision['accepted_option'] is None,'Failure limitation/author boundary missing')
    return {'Failure attribution':dict(status='PASS',detail=
        'Bounded technical attribution qualified against protocol §7: loopback transport, isolated timeout/server/parser outcomes, actual Ollama configuration HTTP 500, SQL retry/persistence/denominators. Crash/OOM unobserved; author decision remains part of artifact acceptance.')}
