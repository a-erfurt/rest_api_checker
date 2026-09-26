"""Read-only Gate-B capture. Never dispatches study requests or writes SQL rows."""
import argparse
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import platform
import subprocess
from types import SimpleNamespace
import urllib.request

from rest_api_checker import preflight
from rest_api_checker.operator_config import load, credentials
from rest_api_checker.persistence.database import connect
from rest_api_checker.persistence.repository import Repository
from rest_api_checker.persistence.importer import load_development
from rest_api_checker.experiment import renderer, request, schedule

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'docs/runtime_qualification_2026-09-26'
RESEARCH = ROOT.parent/'bachelor_rest_api_checker'

def digest(raw):
    return sha256(raw).hexdigest()

def save(name, value):
    (OUT/name).write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')

def command(*args):
    return subprocess.check_output(args, text=True).strip()

def api(path, data=None):
    body = None if data is None else json.dumps(data).encode()
    with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:11434'+path, data=body, headers={'Content-Type':'application/json'}), timeout=300) as r:
        return json.load(r)

def preservation():
    result = {}
    for base, files in [(RESEARCH, command('git','-C',str(RESEARCH),'ls-files','--cached','--others','--exclude-standard').splitlines()),
                        (ROOT, ['docs/development_dataset_v1_release.json','docs/experiment_evidence/comparison_schedule_v1.json','docs/experiment_evidence/artifact_verification.json'] + [str(p.relative_to(ROOT)) for p in (ROOT/'artifacts/development_dataset_v1').rglob('*') if p.is_file()])]:
        for name in files:
            p=base/name
            if p.is_file(): result[str(p)]=digest(p.read_bytes())
    return result

def database():
    config=load(SimpleNamespace())
    cn=connect(credentials(config), config.database)
    try:
        counts={table:cn.execute('SELECT COUNT_BIG(*) FROM dbo.'+table).fetchval() for table in ('test_cases','reference_results','prompts','models','run_configs','experiments','experiment_runs','run_attempts','predictions','evaluation_reports')}
        security={'current_user':cn.execute('SELECT USER_NAME()').fetchval(), 'sysadmin':cn.execute("SELECT IS_SRVROLEMEMBER('sysadmin')").fetchval(), 'role_members':[r[0] for r in cn.execute("SELECT m.name FROM sys.database_role_members r JOIN sys.database_principals p ON p.principal_id=r.role_principal_id JOIN sys.database_principals m ON m.principal_id=r.member_principal_id WHERE p.name='rac_application'")], 'database_principals':[list(r) for r in cn.execute("SELECT name,type_desc FROM sys.database_principals WHERE principal_id>4 AND type IN ('S','U','G')")], 'role_exists':cn.execute("SELECT COUNT(*) FROM sys.database_principals WHERE name='rac_application' AND type='R'").fetchval()}
        result=preflight.check(ROOT,RESEARCH,Repository(cn))
        return dict(counts=counts,security=security,preflight=result)
    finally:
        cn.rollback(); cn.close()

def capture(phase):
    OUT.mkdir(exist_ok=True)
    save('preservation_'+phase+'.json',preservation())
    save('database_'+phase+'.json',database())
    if phase!='before': return
    binaries=['/opt/homebrew/bin/ollama','/Applications/Ollama.app/Contents/Resources/ollama','/Applications/Ollama.app/Contents/Resources/llama-server']
    save('host.json',dict(captured_at=datetime.now().astimezone().isoformat(),timezone=command('date','+%Z'),git_commit=command('git','rev-parse','HEAD'),research_commit=command('git','-C',str(RESEARCH),'rev-parse','HEAD'),os=command('sw_vers'),architecture=platform.machine(),cpu=command('sysctl','-n','machdep.cpu.brand_string'),ram_bytes=int(command('sysctl','-n','hw.memsize')),hardware=command('system_profiler','SPDisplaysDataType'),python=platform.python_version(),ollama=api('/api/version'),binaries={p:dict(sha256=digest(Path(p).read_bytes()),realpath=str(Path(p).resolve())) for p in binaries}))
    tags=api('/api/tags'); save('tags.json',tags); save('ps_before.json',api('/api/ps'))
    identities=[]
    for model,short in zip(request.MODELS,('qwen','gemma','mistral')):
        show=api('/api/show',{'model':model}); save(short+'_show.json',show)
        native=Path.home()/'.ollama/models'
        raw=(native/'manifests/registry.ollama.ai/library'/model.replace(':','/')).read_bytes()
        (OUT/(short+'_manifest.json')).write_bytes(raw)
        manifest=json.loads(raw); layers=[]
        for layer in [manifest['config']]+manifest['layers']:
            p=native/'blobs'/layer['digest'].replace(':','-')
            with p.open('rb') as f:
                h=sha256()
                while chunk:=f.read(8*1024*1024): h.update(chunk)
            measured='sha256:'+h.hexdigest()
            assert measured==layer['digest'] and p.stat().st_size==layer['size']
            layers.append(dict(digest=measured,size=p.stat().st_size,mediaType=layer['mediaType']))
            if layer['size']<100000 and layer['mediaType']!='application/vnd.ollama.image.license':
                (OUT/(short+'_'+layer['mediaType'].rsplit('.',1)[-1]+'.txt')).write_bytes(p.read_bytes())
        tag=next(t for t in tags['models'] if t['name']==model)
        assert tag['digest']==digest(raw)
        (OUT/(short+'_template.txt')).write_text(show['template'])
        identities.append(dict(name=model,digest=tag['digest'],manifest=short+'_manifest.json',show=short+'_show.json',layers=layers,template_sha256=digest(show['template'].encode())))
    save('identities.json',identities)
    manifest,closure=load_development(ROOT/'artifacts/development_dataset_v1',ROOT/'docs/development_dataset_v1_release.json',RESEARCH)
    candidates=json.loads((RESEARCH/'03_research_design/prompt_candidates_v1/candidate_manifest_v1.json').read_bytes())
    prompts={p['id']:(RESEARCH/p['path']).read_bytes() for p in candidates['candidates']}
    rendered={}
    for c in manifest['cases']:
        contract=manifest['sources'][manifest['contracts'][c['api']]]['path']; body=c['body']['path']
        rendered[c['case_id']]=renderer.render(renderer.Evidence(closure[contract],c['operation']['method'],c['operation']['path'],c['status'],c['content_type'],closure[body]),contract_identity=contract,body_identity=body)
    requests=[]
    for slot in schedule.comparison_schedule():
        req=request.build_request(rendered[slot.case],prompt_name=slot.prompt,prompt=prompts[slot.prompt],model=slot.model,model_digest=next(m['digest'] for m in identities if m['name']==slot.model),repetition=slot.repetition)
        request.validate_request(req)
        requests.append(dict(case=slot.case,prompt=slot.prompt,model=slot.model,repetition=slot.repetition,request_sha256=digest(req.body),metadata=req.metadata))
    save('request_inventory.json',dict(dispatched=False,requests=requests))

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('phase',choices=['before','after']); capture(parser.parse_args().phase)
