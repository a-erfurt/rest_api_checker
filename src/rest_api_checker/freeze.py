"""Read-only Gate-B candidate construction and explicit, separately supplied acceptance.

No function here selects prompts, generates answers or writes experiment rows.
"""
from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
import platform
import subprocess
import urllib.request

from . import evaluation, runtime_evidence, gate_b_closure
from .experiment import parser, renderer, request, schedule
from .experiment.encoding import digest, encode
from .persistence.database import require
from .persistence.importer import DEV_HASH, PROMPT_HASHES, load_development
from .persistence.inspection import bindings, portable, rows
from .persistence.migrate import verify

CANDIDATE = 'artifacts/gate_b_freeze_candidate_v1/candidate.json'


def git(root, *args):
    return subprocess.check_output(['git','-C',str(root),*args],text=True).strip()


def principal(cn):
    row=cn.execute("SELECT DB_NAME(),ORIGINAL_LOGIN(),USER_NAME(),IS_SRVROLEMEMBER('sysadmin'),IS_MEMBER('db_owner'),IS_MEMBER('rac_application'),CONVERT(varchar(170),SUSER_SID(),1)").fetchone()
    value=dict(zip(('database','login','user','sysadmin','db_owner','application_role','login_sid'),row))
    require(value['sysadmin']==0 and value['db_owner']==0 and value['application_role']==1,
            'Dedicated application principal required')
    require(cn.execute("SELECT HAS_PERMS_BY_NAME(NULL,NULL,'CONTROL SERVER')").fetchval()==0,
            'Administrative server permission forbidden')
    roles=[r[0] for r in cn.execute("SELECT r.name FROM sys.database_role_members m JOIN sys.database_principals r ON r.principal_id=m.role_principal_id WHERE m.member_principal_id=USER_ID() ORDER BY r.name").fetchall()]
    require(roles==['rac_application'],'Unexpected application role membership')
    value['roles']=roles
    server_roles=[r[0] for r in cn.execute("SELECT r.name FROM sys.server_role_members m JOIN sys.server_principals r ON r.principal_id=m.role_principal_id WHERE m.member_principal_id=SUSER_ID() ORDER BY r.name").fetchall()]
    require(not server_roles,'Unexpected server role membership')
    value['server_roles']=server_roles
    value['role_permissions']=[list(r) for r in cn.execute("SELECT p.class_desc,CASE WHEN p.class=3 THEN SCHEMA_NAME(p.major_id) ELSE OBJECT_NAME(p.major_id) END,COL_NAME(p.major_id,p.minor_id),p.permission_name,p.state_desc FROM sys.database_permissions p WHERE p.grantee_principal_id=DATABASE_PRINCIPAL_ID('rac_application') ORDER BY p.class,p.major_id,p.minor_id,p.permission_name").fetchall()]
    direct=[list(r) for r in cn.execute("SELECT class_desc,permission_name,state_desc FROM sys.database_permissions WHERE grantee_principal_id=USER_ID() ORDER BY permission_name").fetchall()]
    require(direct==[['DATABASE','CONNECT','GRANT']],
            'Unexpected direct application-user permission')
    value['direct_permissions']=direct
    for permission in ('ALTER ANY LOGIN','ALTER ANY SERVER ROLE','CREATE ANY DATABASE'):
        require(cn.execute('SELECT HAS_PERMS_BY_NAME(NULL,NULL,?)',permission).fetchval()==0,
                'Unexpected server administrative permission')
    return value


def source_hashes(root, research):
    old=root/runtime_evidence.DIRECTORY
    bundle=json.loads((old/'bundle.json').read_bytes())
    sources=dict(bundle['sources'])
    for name in bundle['files']:
        relative=runtime_evidence.DIRECTORY+'/'+name
        sources['implementation:'+relative]=digest((root/relative).read_bytes())
    sources['implementation:'+runtime_evidence.DIRECTORY+'/bundle.json']=digest((old/'bundle.json').read_bytes())
    for pattern in ('src/**/*.py','src/**/*.json','src/**/*.sql','tools/gate_b_closure/*.py'):
        for p in root.glob(pattern): sources['implementation:'+str(p.relative_to(root))]=digest(p.read_bytes())
    for name in ('pyproject.toml','uv.lock'):
        sources['implementation:'+name]=digest((root/name).read_bytes())
    closure=root/gate_b_closure.DIRECTORY
    for name in ('bundle.json', *json.loads((closure/'bundle.json').read_bytes())['files']):
        sources['implementation:'+gate_b_closure.DIRECTORY+'/'+name]=digest((closure/name).read_bytes())
    return sources


def check_sources(candidate, root, research):
    require(candidate['sources'], 'Empty freeze closure')
    for key, sha in candidate['sources'].items():
        base, relative=key.split(':',1)
        require(base in ('implementation','research') and not Path(relative).is_absolute()
                and '..' not in Path(relative).parts, 'Unsafe freeze source')
        path=(root if base=='implementation' else research)/relative
        require(digest(path.read_bytes())==sha, 'Freeze source drift: '+key)


def build(repo, root, research, registrations):
    """Candidate only: SELECTs and local bytes, no SQL schedule materialization."""
    runtime=runtime_evidence.inspect(root,research)
    require(all(runtime[n]['status']=='PASS' for n in
        ('Full model identities','Template and effective options','Context fit')), 'Runtime evidence incomplete')
    require(gate_b_closure.inspect(root,research)['Failure attribution']['status']=='PASS','Technical closure incomplete')
    require(not git(root,'status','--porcelain','--untracked-files=no'), 'Commit implementation before candidate construction')
    for table in ('experiments','experiment_runs','run_attempts','predictions','evaluation_reports'):
        require(not rows(repo,table), 'Study database is not empty: '+table)
    security=principal(repo.cn)
    require(security['database']=='rest_api_checker', 'Wrong target application database')
    manifest, closure=load_development(root/'artifacts/development_dataset_v1',root/'docs/development_dataset_v1_release.json',research)
    datasets=[d for d in rows(repo,'datasets') if (d['name'],d['version'],d['purpose'])==('development_dataset','v1','development')]
    require(len(datasets)==1, 'Dataset identity')
    dataset=datasets[0]
    members=sorted(rows(repo,'dataset_cases',dataset_id=dataset['id']),key=lambda m:m['position'])
    require([m['case_code'] for m in members]==list(schedule.CASES),'Membership identity/order')
    prompts={p['name']:p for p in rows(repo,'prompts')}
    require(set(prompts)==set(PROMPT_HASHES),'Prompt roster')
    for name, p in prompts.items():
        require(digest(repo.file(p['file_id']))==PROMPT_HASHES[name], 'SQL prompt drift')
    rendered={}
    references=[]
    cases={c['case_id']:c for c in manifest['cases']}
    for member in members:
        code=member['case_code']; source=cases[code]
        case=repo._row('test_cases',member['case_id'])
        ref=repo._row('reference_results',member['reference_id'])
        require(ref['case_id']==case['id'] and ref['version']==1
                and digest(repo.file(ref['source_file_id']))==DEV_HASH,'Reference revision/source drift')
        require(repo.source(case['source_file_id'],case['source_pointer'])==source,'SQL case source drift')
        require(repo.source(ref['source_file_id'],ref['source_pointer'])==source['oracle']
                and all(ref[c]==source['oracle'][c] for c in ('c1','c2','c3')), 'SQL reference vector drift')
        operation=repo._row('api_operations',case['operation_id'])
        contract=repo._row('api_contracts',operation['contract_id'])
        response=repo._row('responses',case['response_id'])
        ev=renderer.Evidence(repo.file(contract['file_id']),operation['http_method'],operation['path_template'],
                            response['status_code'],response['content_type'],repo.file(response['body_file_id']))
        rendered[code]=renderer.render(ev,contract_identity=f'files:{contract["file_id"]}',body_identity=f'files:{response["body_file_id"]}')
        references.append(dict(case=code,membership=member,reference=ref))
    old=root/runtime_evidence.DIRECTORY
    identities=json.loads((old/'identities.json').read_bytes())
    contexts=json.loads((old/'context.json').read_bytes())['rows']
    model_rows={name:repo._row('models',registrations['models'][name]) for name in request.MODELS}
    for identity in identities:
        name=identity['name']; row=model_rows[name]
        require(row['digest']==identity['digest'] and row['quantization']=='Q4_K_M'
                and repo.file(row['metadata_file_id'])==(old/identity['show']).read_bytes(), 'SQL model drift')
        repo.require_d07(registrations['configs'][name],name)
    member_ids={m['case_code']:m['id'] for m in members}
    sql_schedule=[]; proofs={}
    for slot in schedule.comparison_schedule():
        req=request.build_request(rendered[slot.case],prompt_name=slot.prompt,prompt=repo.file(prompts[slot.prompt]['file_id']),
            model=slot.model,model_digest=model_rows[slot.model]['digest'],repetition=slot.repetition)
        request.validate_request(req)
        measured=next(c for c in contexts if c['run_order']==slot.run_order)
        require(measured['request_sha256']==digest(req.body),'SQL/source rendered request drift')
        proof=request.ContextProof(digest(req.body),measured['model_digest'],measured['template_sha256'],
                                   digest((old/'context.json').read_bytes()),measured['input_tokens'])
        proof.verify(req); proofs[str(slot.run_order)]=asdict(proof)
        sql_schedule.append(dict(dataset_case_id=member_ids[slot.case],model_id=registrations['models'][slot.model],
            prompt_id=prompts[slot.prompt]['id'],run_config_id=registrations['configs'][slot.model],repetition=slot.repetition,seed=slot.seed,run_order=slot.run_order))
    result=dict(format='gate-b-freeze-candidate-v1',status='NOT AUTHOR-ACCEPTED',instruction='DO NOT EXECUTE',gate_b_complete=False,
        phase='prompt_comparison_development',created_at=datetime.now().astimezone().isoformat(),
        implementation_commit=git(root,'rev-parse','HEAD'),research_commit=git(research,'rev-parse','HEAD'),
        research_working_tree=git(research,'status','--porcelain'),sources=source_hashes(root,research),
        dataset=dataset,dataset_manifest_sha256=DEV_HASH,references=references,prompts={p:PROMPT_HASHES[p] for p in schedule.PROMPTS},
        models=identities,runtime=json.loads((old/'host.json').read_bytes()),native_runner=json.loads((old/'runtime_build.json').read_bytes()),
        configuration=dict(options=request.OPTIONS,stream=False,timeout_seconds=request.TIMEOUT,seeds={str(k):v for k,v in request.SEEDS.items()},
                           thinking={m:False if m==request.MODELS[0] else 'OMIT' for m in request.MODELS}),
        renderer=dict(version=renderer.VERSION,sha256=renderer.artifact_hash()),parser=dict(version=parser.VERSION,sha256=parser.artifact_hash()),
        evaluator=dict(version=evaluation.VERSION,sha256=evaluation.artifact_hash()),input_policy='Protocol D01/D05; one complete frozen system prompt + one losslessly rendered operation/response evidence user message; native templates; no history/tools/images/format constraint',
        database=dict(schema_version=verify(repo.cn),principal=security),schedule_seed=schedule.SCHEDULE_SEED,
        schedule_sha256=digest(schedule.dry_run_bytes()),schedule_version=schedule.VERSION,expected_runs=324,
        portable_schedule=[asdict(s) for s in schedule.comparison_schedule()],schedule=sql_schedule,
        context_proofs=proofs,context_evidence_sha256=digest((old/'context.json').read_bytes()),
        bindings=bindings(repo,dataset['id'],sql_schedule),
        parser_sha256=parser.artifact_hash(),renderer_sha256=renderer.artifact_hash(),dataset_id=dataset['id'],
        author_decisions=['Accept bounded failure qualification with crash/OOM unobserved OR require additional safe diagnostic','Accept this exact candidate hash and execution commit separately'],
        selected_prompt=None,sensitivity_variant=None)
    # Retain every archived source byte by identity, plus filesystem source closure.
    result['files']=[dict(file_id=r['id'],name=r['name'],size_bytes=r['size_bytes'],sha256=digest(repo.file(r['id']))) for r in rows(repo,'files')]
    repo.cn.rollback()
    return portable(result)


def verify_candidate(candidate, root, research, repo=None):
    require(candidate['format']=='gate-b-freeze-candidate-v1'
            and candidate['status']=='NOT AUTHOR-ACCEPTED' and candidate['instruction']=='DO NOT EXECUTE'
            and candidate['gate_b_complete'] is False, 'Candidate must remain non-executable')
    check_sources(candidate,root,research)
    require(candidate['sources']==source_hashes(root,research),'Incomplete freeze source closure')
    require(gate_b_closure.inspect(root,research)['Failure attribution']['status']=='PASS','Technical qualification invalid')
    old=root/runtime_evidence.DIRECTORY
    for key,name in (('models','identities.json'),('runtime','host.json'),('native_runner','runtime_build.json')):
        require(candidate[key]==json.loads((old/name).read_bytes()),'Candidate runtime identity drift: '+key)
    require(candidate['prompts']==PROMPT_HASHES and candidate['dataset_manifest_sha256']==DEV_HASH,
            'Candidate scientific source identity drift')
    require(candidate['implementation_commit']==git(root,'rev-parse','HEAD'),'Execution commit drift')
    require(not git(root,'status','--porcelain','--untracked-files=no'),'Uncommitted implementation changes')
    require(candidate['schedule_sha256']==digest(schedule.dry_run_bytes())
            and candidate['portable_schedule']==json.loads(schedule.dry_run_bytes())['slots'],'Schedule drift')
    require(candidate['configuration']==json.loads(encode(dict(options=request.OPTIONS,stream=False,timeout_seconds=request.TIMEOUT,
        seeds={str(k):v for k,v in request.SEEDS.items()},thinking={m:False if m==request.MODELS[0] else 'OMIT' for m in request.MODELS}))), 'Configuration drift')
    require(candidate['parser']['sha256']==parser.artifact_hash() and candidate['renderer']['sha256']==renderer.artifact_hash()
            and candidate['evaluator']['sha256']==evaluation.artifact_hash(),'Scientific implementation drift')
    require(candidate['selected_prompt'] is None and candidate['sensitivity_variant'] is None,'Premature selection')
    require(candidate['expected_runs']==324 and candidate['schedule_seed']==schedule.SCHEDULE_SEED
            and candidate['dataset_id']==candidate['dataset']['id'], 'Schedule/dataset identity')
    measured=json.loads((root/runtime_evidence.DIRECTORY/'context.json').read_bytes())['rows']
    expected_proofs={str(row['run_order']):dict(request_sha256=row['request_sha256'],model_digest=row['model_digest'],
        template_sha256=row['template_sha256'],measurement_sha256=candidate['context_evidence_sha256'],input_tokens=row['input_tokens']) for row in measured}
    require(candidate['context_evidence_sha256']==digest((root/runtime_evidence.DIRECTORY/'context.json').read_bytes())
            and candidate['context_proofs']==expected_proofs,'Context coverage/measurement drift')
    bound=candidate['bindings']
    members={r['case_code']:r['id'] for r in bound['dataset_cases']}
    prompts={r['name']:r['id'] for r in bound['prompts']}
    models={r['name']:r['id'] for r in bound['models']}
    config_ids={m:next(row['run_config_id'] for row in candidate['schedule'] if row['model_id']==i) for m,i in models.items()}
    expected=[dict(dataset_case_id=members[s.case],prompt_id=prompts[s.prompt],model_id=models[s.model],
        run_config_id=config_ids[s.model],repetition=s.repetition,seed=s.seed,run_order=s.run_order) for s in schedule.comparison_schedule()]
    require(candidate['schedule']==expected,'SQL/portable schedule mismatch')
    if repo is not None:
        require(principal(repo.cn)==candidate['database']['principal'],'Application principal drift')
        require(verify(repo.cn)==candidate['database']['schema_version'],'Schema drift')
        require(bindings(repo,candidate['dataset']['id'],candidate['schedule'])==candidate['bindings'],'SQL source/reference binding drift')
        for model,config in config_ids.items(): repo.require_d07(config,model)
        repo.verify_closure(candidate['files']); repo.cn.rollback()
    return True


def require_acceptance(candidate_raw, record):
    """Consume an explicit author record; never create or infer author approval."""
    require(record.get('decision')=='AUTHOR_ACCEPTED_FOR_PROMPT_COMPARISON'
            and record.get('candidate_sha256')==digest(candidate_raw)
            and record.get('failure_qualification')=='ACCEPT_BOUNDED_EVIDENCE_WITH_UNOBSERVED_CRASH_OOM',
            'Explicit hash-bound author acceptance required')
    require(type(record.get('author')) is str and bool(record['author'].strip()), 'Named author required')
    timestamp=datetime.fromisoformat(record['accepted_at'])
    require(timestamp.tzinfo is not None, 'Offset-qualified author acceptance time required')
    return True


def verify_live(candidate, root, api=None):
    """Metadata only. No pulls, model loading, tokenization or generation."""
    if api is None:
        def api(path,data=None):
            body=None if data is None else encode(data)
            with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:11434'+path,data=body,
                    headers={'Content-Type':'application/json'}),timeout=15) as response:
                return json.load(response)
    host=candidate['runtime']
    require(api('/api/version')==host['ollama'],'Ollama version drift')
    require(platform.machine()==host['architecture'],'Host architecture drift')
    require(platform.python_version()==host['python'],'Python runtime drift')
    for args,expected in ((['sw_vers'],host['os']),(['sysctl','-n','machdep.cpu.brand_string'],host['cpu']),
                          (['sysctl','-n','hw.memsize'],str(host['ram_bytes']))):
        require(subprocess.check_output(args,text=True).strip()==expected,'Host OS/CPU/RAM drift')
    graphics=subprocess.check_output(['system_profiler','SPDisplaysDataType'],text=True).strip()
    # Displays may be attached/detached; bind accelerator/Metal identity before
    # the display inventory, which is irrelevant to generation.
    require(graphics.split('      Displays:')[0].strip()==host['hardware'].split('      Displays:')[0].strip(),
            'GPU/Metal identity drift')
    for path,identity in host['binaries'].items():
        require(digest(Path(path).read_bytes())==identity['sha256'],'Runtime binary drift')
    tags=api('/api/tags')['models']
    for identity in candidate['models']:
        tag=next((t for t in tags if t['name']==identity['name']),{})
        require(tag.get('digest')==identity['digest'],'Live model digest drift')
        expected=json.loads((root/runtime_evidence.DIRECTORY/identity['show']).read_bytes())
        require(api('/api/show',{'model':identity['name']})==expected,'Native metadata/template/default drift')
    return True
