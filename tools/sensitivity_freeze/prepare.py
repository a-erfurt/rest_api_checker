"""Prepare only: native render/tokenize measurements, SELECTs, immutable local files.

Run after committing this tool. An existing directory is never overwritten.
No execution/acceptance command is implemented here.
"""
from contextlib import closing
from datetime import datetime
import json
from pathlib import Path
import re
import subprocess
import urllib.request

from rest_api_checker import freeze, sensitivity_freeze as sf
from rest_api_checker.experiment.encoding import digest, encode
from rest_api_checker.persistence.database import connect, read_settings, require
from rest_api_checker.persistence.repository import Repository

ROOT=Path(__file__).resolve().parents[2]
RESEARCH=ROOT.parent/'bachelor_rest_api_checker'


def post(url, payload):
    """Fail closed: only native render-only chat and tokenization can be sent."""
    require(url=='http://127.0.0.1:11434/api/chat'
            and payload.get('_debug_render_only') is True and payload.get('truncate') is False
            or re.fullmatch(r'http://127\.0\.0\.1:\d+/tokenize',url)
            and set(payload)=={'content','add_special','parse_special'}
            and payload['add_special'] is True and payload['parse_special'] is True,
            'Only render-only and tokenize requests allowed')
    with urllib.request.urlopen(urllib.request.Request(url,data=encode(payload),
            headers={'Content-Type':'application/json'}),timeout=300) as response:
        return json.load(response)


def save(directory, name, value):
    p=directory/name;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('xb') as f: f.write(value if isinstance(value,bytes) else encode(value))


def measure(directory,candidate,requests):
    rows=[]
    for slot in candidate['portable_schedule']:
        order=slot['run_order'];req=requests[order]
        save(directory,f'requests/{order:03}.json',req.body)
        identity=next(m for m in candidate['models'] if m['name']==slot['model'])
        debug=post('http://127.0.0.1:11434/api/chat',
                   {**json.loads(req.body),'_debug_render_only':True,'truncate':False})
        require(not debug.get('done') and not debug.get('eval_count')
                and not debug.get('message',{}).get('content')
                and not debug.get('message',{}).get('thinking'), 'Unexpected completion')
        require(not debug['_debug_info'].get('image_count'),'Unexpected image')
        text=debug['_debug_info']['rendered_template']
        blob=next(l['digest'] for l in identity['layers'] if l['mediaType']=='application/vnd.ollama.image.model').replace(':','-')
        runners=[l for l in subprocess.check_output(['ps','-axo','args'],text=True).splitlines()
                 if '/llama-server --model ' in l and blob in l]
        require(len(runners)==1,'Exact native model runner required')
        port=re.search(r'--port (\d+)',runners[0])[1]
        tokens=post('http://127.0.0.1:'+port+'/tokenize',
                    dict(content=text,add_special=True,parse_special=True))
        require(type(tokens['tokens']) is list and tokens['tokens']
                and all(type(t) is int for t in tokens['tokens']),'Native token ids required')
        count=len(tokens['tokens']);require(count+512<=32768,'Context overflow')
        render_path=f'native/{order:03}_render.json';tokens_path=f'native/{order:03}_tokens.json'
        save(directory,render_path,debug);save(directory,tokens_path,tokens)
        rows.append(dict(**slot,request_sha256=digest(req.body),input_tokens=count,total_tokens=count+512,
            margin=32768-count-512,model_digest=identity['digest'],template_sha256=identity['template_sha256'],
            rendered_sha256=digest(text.encode()),tokens_sha256=digest(encode(tokens['tokens'])),
            render_path=render_path,tokens_path=tokens_path,runner_command=runners[0]))
        if order%12==0: print(json.dumps(dict(measured=order,model=slot['model'],last_input_tokens=count)),flush=True)
    maxima={m:max(r['input_tokens'] for r in rows if r['model']==m) for m in sf.request.MODELS}
    save(directory,'context.json',dict(captured_at=datetime.now().astimezone().isoformat(),
        method='Qualified Ollama 0.34.4 _debug_render_only + exact live native runner /tokenize; add_special=true, parse_special=true; measured every repetition.',
        render_only_calls=108,tokenize_calls=108,study_generation_calls=0,max_input_tokens=maxima,rows=rows))
    return maxima


def main():
    directory=ROOT/sf.DIRECTORY
    require(not directory.exists(),'Preserve existing evidence; choose an explicitly reviewed new version')
    with closing(connect(read_settings(Path.home()/'.config/rest-api-checker/application-credentials.env'),'rest_api_checker')) as cn:
        repo=Repository(cn)
        candidate,requests=sf.prepare(repo,ROOT,RESEARCH)
        freeze.verify_live(candidate,ROOT)
        directory.mkdir(parents=True)
        save(directory,'database_before.json',candidate['database']['before'])
        save(directory,'schedule.json',sf.schedule_bytes())
        save(directory,'request_inventory.json',candidate['request_inventory'])
        maxima=measure(directory,candidate,requests)
        freeze.verify_live(candidate,ROOT)
        after=sf.snapshot(repo);cn.rollback()
        save(directory,'database_after.json',after)
        require(after==candidate['database']['before'],'Database changed during measurement')
        candidate['context_evidence_sha256']=digest((directory/'context.json').read_bytes())
        candidate['context_max_input_tokens']=maxima
        candidate['artifacts']={str(p.relative_to(directory)):digest(p.read_bytes()) for p in sorted(directory.rglob('*')) if p.is_file()}
        sf.verify_bundle(candidate,ROOT,RESEARCH,directory,repo)
        raw=encode(candidate)
        save(directory,'candidate.json',raw)
        save(directory,'candidate.sha256',(digest(raw)+'  candidate.json\n').encode())
        save(directory,'verification.json',dict(candidate_sha256=digest(raw),verified_at=datetime.now().astimezone().isoformat(),
            status='PASS_CANDIDATE_ONLY',database_unchanged=True,live_runtime_unchanged=True,
            requests_reconstructed=108,requests_measured=108,semantic_generations=0,
            sensitivity_experiments_created=0,sensitivity_runs_persisted=0,evaluation_executed=False,
            execution_blockers=candidate['execution_blockers']))
        print(json.dumps(dict(candidate=str(directory/'candidate.json'),sha256=digest(raw),
            schedule_sha256=candidate['schedule_sha256'],context_maxima=maxima,status=candidate['status']),indent=2))

if __name__=='__main__':main()
