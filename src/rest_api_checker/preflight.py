"""Read-only, offline Gate-B checks. Runtime evidence is never inferred from mocks."""
import json
from itertools import product

from .experiment import parser, renderer, schedule
from .experiment.encoding import digest, encode
from .persistence.database import require
from .persistence.importer import load_development, read_bound, PROMPT_HASHES
from .persistence.inspection import bindings, status
from .persistence.migrate import verify
from . import runtime_evidence


def check(root, research, repo=None, experiment_id=None):
    checks, loaded = [], {}
    def run(name, fn):
        try:
            detail = fn()
            checks.append(dict(check=name,status='PASS',detail=detail))
        except (ValueError, OSError, KeyError, TypeError) as exc:
            checks.append(dict(check=name,status='FAIL',detail=str(exc)))
    def development():
        manifest, closure = load_development(root/'artifacts/development_dataset_v1',root/'docs/development_dataset_v1_release.json',research)
        loaded.update(manifest=manifest,closure=closure)
        return f'12 released cases; {digest(closure["manifest.json"])}'
    run('Development dataset hash and release',development)
    def prompts():
        m = json.loads((research/'03_research_design/prompt_candidates_v1/candidate_manifest_v1.json').read_bytes())
        require(m['approval']['exact_texts']=='AUTHOR_APPROVED','Exact prompt approval missing')
        for d in m['candidates']+m['shared_blocks']+[m['protocol_binding'],m['semantic_equivalence_review'],m['approval']['exact_text_approval_record']]:
            read_bound(research,d)
        require({p['id']:p['sha256'] for p in m['candidates']}==PROMPT_HASHES,'Prompt roster/hash mismatch')
        return 'P1/P2/P3 exact approved bytes and source bindings'
    run('P1/P2/P3 hashes',prompts)
    def rendering():
        manifest, closure = loaded['manifest'], loaded['closure']
        recorded = json.loads((root/'docs/experiment_evidence/artifact_verification.json').read_bytes())
        actual = []
        for c in manifest['cases']:
            contract = manifest['sources'][manifest['contracts'][c['api']]]['path']
            body = c['body']['path']
            ev = renderer.Evidence(closure[contract],c['operation']['method'],c['operation']['path'],c['status'],c['content_type'],closure[body])
            rendered = renderer.render(ev,contract_identity=contract,body_identity=body)
            actual.append(dict(case=c['case_id'],**rendered.metadata))
            require(json.loads(rendered.content)['observed_response']['body'].encode()==closure[body],'Body round-trip failed')
        require(actual==recorded['inputs'],'Renderer verification artifact drift')
        try:
            renderer.render({'evidence':ev,'reference':'FORBIDDEN'},contract_identity='probe',body_identity='probe')
        except (ValueError,TypeError):
            pass
        else:
            raise ValueError('Renderer accepted domain metadata')
        return '12 exact input hashes, complete closure, byte round-trip and allowlist rejection verified'
    run('Renderer closure / leakage boundary',rendering)
    def parsing():
        recorded = json.loads((root/'docs/experiment_evidence/artifact_verification.json').read_bytes())
        require(recorded['parser_sha256']==parser.artifact_hash(),'Parser hash changed')
        for vector in product(('PASS','FAIL','NOT_APPLICABLE'),repeat=3):
            value = encode({c:dict(verdict=v,reason='probe') for c,v in zip(('c1','c2','c3'),vector)}).decode()
            require(parser.parse(value).status=='VALID_OUTPUT','Legal verdict rejected')
        for value in ('','{}','```{} ```','{"c1":{},"c1":{}}'):
            require(parser.parse(value).status=='PARSER_FAILURE','Malformed answer admitted')
        return f'{parser.VERSION}; {parser.artifact_hash()}; 27 legal vectors and rejection probes'
    run('Parser version and acceptance',parsing)
    def planned():
        require((root/'docs/experiment_evidence/comparison_schedule_v1.json').read_bytes()==schedule.dry_run_bytes(),'Schedule artifact drift')
        return '324 logical runs; 108 per prompt; non-dispatched schedule only'
    run('Schedule: 324 logical runs',planned)
    if repo:
        run('Database schema',lambda: f'version {verify(repo.cn)}; migration checksums verified')
        if experiment_id is not None:
            def bound():
                s = status(repo,experiment_id)
                setup = json.loads(repo.file(s['experiment']['setup_file_id']))
                require(setup.get('bindings')==bindings(repo,s['experiment']['dataset_id'],setup['schedule']),'Frozen binding drift')
                require(s['planned']==324,'Comparison schedule incomplete')
                return f'{s["completed"]}/324 completed; fabricated={s["fabricated"]}'
            run('Persisted schedule and bindings',bound)
        repo.cn.commit()
    else:
        checks.append(dict(check='Database schema',status='BLOCKED',detail='No database supplied; not verified'))
    try:
        runtime = runtime_evidence.inspect(root, research)
    except (ValueError, OSError, KeyError, TypeError, StopIteration) as exc:
        runtime = {name: dict(status='FAIL', detail='Runtime evidence invalid: '+str(exc))
                   for name in ('Full model identities', 'Template and effective options',
                                'Context fit', 'Failure attribution')}
    for name, detail in (
        ('Full model identities','Actual full manifests, Q4_K_M and runtime/hardware evidence not verified'),
        ('Template and effective options','Native templates, defaults, D07 support and thinking policy require measured evidence'),
        ('Context fit','Actual tokenizer/template-aware measurements for every complete request are absent'),
        ('Failure attribution','Real runtime-specific isolated/systematic failure evidence remains unverified'),
        ('Gate-B artifact acceptance','Complete setup/source closure, application-role deployment and author freeze acceptance pending')):
        checks.append(dict(check=name, **runtime.get(name, dict(status='BLOCKED',detail=detail))))
    return dict(gate='B',status='FAIL' if any(c['status']=='FAIL' for c in checks) else 'BLOCKED',
                inference_performed=False,checks=checks)
