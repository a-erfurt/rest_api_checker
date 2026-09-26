"""Offline descriptive analysis only. No DB/network/provider/evaluator calls.
Usage: PYTHONDONTWRITEBYTECODE=1 REPO/.venv/bin/python root_cause_reproduce.py REPO RESEARCH NEW_OUT
Never imports the experimental parser, never creates predictions or scores.
Fence-only inspection uses a temporary string; original content is preserved.
"""
import base64
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import re
import statistics
import struct
import sys

root, research, out = map(Path, sys.argv[1:])
sys.path.insert(0, str(root/'src'))
from rest_api_checker.persistence.importer import load_development
from rest_api_checker.experiment import renderer, request
from rest_api_checker.experiment.encoding import encode

base=root/'docs/experiment_evidence/prompt_comparison_exp1_2026-09-26'
runtime=root/'docs/runtime_qualification_2026-09-26'
def h(b): return sha256(b).hexdigest()
def read(p): return json.loads(p.read_bytes())
def save(name,obj):
    with (out/name).open('x') as f: json.dump(obj,f,indent=2,sort_keys=True);f.write('\n')
out.mkdir(parents=True,exist_ok=False)
data=read(base/'comparison-analysis-input.json');raw=read(base/'raw_outputs.json')
setup=data['setup'];runs={r['id']:r for r in data['runs']}
files={f['file_id']:f for f in data['files']}
assert data['experiment_id']==1 and data['fabricated'] is False and len(raw)==len(runs)==324
for line in (base/'SHA256SUMS').read_text().splitlines():
    expected,name=line.split(None,1); assert h((base/name.strip()).read_bytes())==expected,name
for key,expected in setup['sources'].items():
    kind,rel=key.split(':',1);p=({'implementation':root,'research':research})[kind]/rel
    assert h(p.read_bytes())==expected,key
assert renderer.artifact_hash()==setup['renderer_sha256']
manifest,closure=load_development(root/'artifacts/development_dataset_v1',root/'docs/development_dataset_v1_release.json',research)
candidates=read(research/'03_research_design/prompt_candidates_v1/candidate_manifest_v1.json')
prompts={p['id']:(research/p['path']).read_bytes() for p in candidates['candidates']}
assert {k:h(v) for k,v in prompts.items()}==setup['prompts']
for p in prompts.values():
    assert b'Return exactly one JSON object with exactly the keys "c1", "c2" and "c3".' in p
    assert b'Return no Markdown fences, surrounding prose, confidence score, overall verdict or metadata.' in p
slot_checks=[]
for short in ('qwen','gemma','mistral'):
    for rep,seed in [(1,101),(2,202),(3,303)]:
        name=short+('' if rep==1 else '_seed'+str(seed))+'_slots.json'
        slot=read(runtime/name)[0];p=slot['params']
        assert slot['n_ctx']==32768 and slot['speculative'] is False
        for key,value in [('seed',seed),('top_k',40),('min_p',0.0),('repeat_penalty',1.0),('repeat_last_n',64),('n_predict',512),('max_tokens',512),('speculative.types','none')]:assert p[key]==value,(name,key)
        for key,value in [('temperature',0.2),('top_p',0.9)]:assert p[key]==struct.unpack('f',struct.pack('f',value))[0]
        slot_checks.append({'file':name,'sha256':h((runtime/name).read_bytes()),'seed':seed,'D07_checked':True})
rendered={}
for c in manifest['cases']:
    contract=manifest['sources'][manifest['contracts'][c['api']]]['path'];body=c['body']['path']
    rendered[c['case_id']]=renderer.render(renderer.Evidence(closure[contract],c['operation']['method'],c['operation']['path'],c['status'],c['content_type'],closure[body]),contract_identity=contract,body_identity=body)
contexts={r['request_sha256']:r for r in read(runtime/'context.json')['rows']}
inventory={r['request_sha256']:r for r in read(runtime/'request_inventory.json')['requests']}
models={m['name']:m for m in setup['models']}
case_records={c['native_case_id']:c for c in data['bindings']['test_cases']}
response_records={r['id']:r for r in data['bindings']['responses']}
operation_records={o['id']:o for o in data['bindings']['api_operations']}
contract_records={c['id']:c for c in data['bindings']['api_contracts']}
def native(model,messages):
    s,u=[x['content'] for x in messages]
    if model=='gemma3:27b':return '<start_of_turn>user\n'+s+'<end_of_turn>\n<start_of_turn>user\n'+u+'<end_of_turn>\n<start_of_turn>model\n'
    if model=='mistral-small3.2:24b':return '[SYSTEM_PROMPT]'+s+'[/SYSTEM_PROMPT][INST]'+u+'[/INST]'
    return None
for short,model in [('gemma','gemma3:27b'),('mistral','mistral-small3.2:24b')]:
    d=read(runtime/f'{short}_diagnostic_request.json')
    # Request evidence may wrap the HTTP payload.
    if 'messages' not in d: d=d.get('request',d.get('payload',d))
    assert native(model,d['messages'])==read(runtime/f'{short}_diagnostic_render.json')['_debug_info']['rendered_template']
def unique(pairs):
    d={}
    for k,v in pairs:
        if k in d:raise ValueError('duplicate key')
        d[k]=v
    return d
def invalid(x):raise ValueError('non-JSON constant '+x)
def parse_json(s):return json.loads(s,object_pairs_hook=unique,parse_constant=invalid)
def shape(v):
    return (type(v) is dict and set(v)=={'c1','c2','c3'} and all(type(i) is dict and set(i)=={'verdict','reason'} and i['verdict'] in ('PASS','FAIL','NOT_APPLICABLE') and type(i['reason']) is str and bool(i['reason'].strip()) for i in v.values()))
rows=[];reconstructed=[];representatives=[];prompt_token_mismatches=[]
for r in raw:
    run=runs[r['run_id']];a=run['attempts'][0]
    assert len(run['attempts'])==1 and a['id']==r['attempt_id'] and a['attempt']==1
    assert all(run[k]==r[k] for k in ['case','model','prompt','repetition','seed','result'])
    rb=base64.b64decode(r['response_base64'],validate=True);env=json.loads(rb)
    assert h(rb)==r['response_sha256']==files[r['response_file_id']]['sha256']
    assert env['message']['content']==r['content']==r['diagnostic']['final_content']
    assert env==r['diagnostic']['provider_metadata']
    assert env['done'] is True and r['diagnostic']['transport']['http_status']==200
    assert a['prompt_tokens']==env['prompt_eval_count'] and a['output_tokens']==env['eval_count'] and a['done_reason']==env['done_reason']
    sp=Path(r['spool_path']).read_bytes();assert h(sp)==r['spool_sha256']
    payload=json.loads(sp)['payload'];assert base64.b64decode(payload['response_base64'])==rb
    req=request.build_request(rendered[r['case']],prompt_name=r['prompt'],prompt=prompts[r['prompt']],model=r['model'],model_digest=models[r['model']]['digest'],repetition=r['repetition'])
    request.validate_request(req);rh=h(req.body)
    assert rh==files[a['request_file_id']]['sha256']==payload['request_sha256']==r['diagnostic']['request_sha256']
    assert req.metadata==inventory[rh]['metadata']
    cr=case_records[r['case']]
    persisted_metadata=dict(req.metadata,contract_identity='files:'+str(contract_records[operation_records[cr['operation_id']]['contract_id']]['file_id']),body_identity='files:'+str(response_records[cr['response_id']]['body_file_id']))
    assert h(encode(persisted_metadata))==r['diagnostic']['transport']['request_provenance_sha256']
    q=json.loads(req.body);ctx=contexts[rh]
    assert q['options']==dict(setup['configuration']['options'],seed=r['seed'])
    assert q['stream'] is False and len(q['messages'])==2
    assert set(q)==({'model','stream','messages','options','think'} if r['model'].startswith('qwen') else {'model','stream','messages','options'})
    nt=native(r['model'],q['messages'])
    if nt is not None:assert h(nt.encode())==ctx['rendered_sha256']
    if env['prompt_eval_count']!=ctx['input_tokens']:prompt_token_mismatches.append(r['run_id'])
    recon=dict(run_id=r['run_id'],model=r['model'],prompt=r['prompt'],case=r['case'],repetition=r['repetition'],request_file_id=a['request_file_id'],request_sha256=rh,native_render_sha256=ctx['rendered_sha256'],native_render_reconstructed=nt is not None,qualified_input_tokens=ctx['input_tokens'],actual_prompt_tokens=env['prompt_eval_count'])
    reconstructed.append(recon)
    if r['case']=='DEV-02' and r['repetition']==1:
        stem=f"{r['model'].split(':')[0]}_{r['prompt']}_DEV-02_R1"
        (out/(stem+'_request.json')).write_bytes(req.body)
        if nt is not None:(out/(stem+'_native.txt')).write_bytes(nt.encode())
        representatives.append(recon|{'request_artifact':stem+'_request.json','native_artifact':stem+'_native.txt' if nt is not None else None,'raw_content':r['content'],'response_sha256':r['response_sha256']})
    s=r['content'];matches=list(re.finditer(r'^```[^\n]*\n(.*?)\n```',s,re.M|re.S))
    closed=len(matches)==1;match=matches[0] if closed else None
    before=s[:match.start()] if match else None;after=s[match.end():] if match else None
    syntax=None;sh=None;error=None
    if match:
        # Delete exactly the two delimiter lines, retaining any surrounding text.
        candidate=before+match.group(1)+after
        try:v=parse_json(candidate);syntax=True;sh=shape(v)
        except (ValueError,TypeError):syntax=False;sh=False
    try:v=parse_json(s);raw_valid=True
    except ValueError as e:raw_valid=False;error=str(e)
    category='RAW_JSON' if raw_valid else ('FENCED_JSON' if match else ('INCOMPLETE_JSON_STRING_AT_CAP' if error.startswith('Unterminated string') else 'EXTRA_TEXT_AFTER_JSON_AT_CAP' if error.startswith('Extra data') else 'OTHER'))
    rows.append({k:r[k] for k in ['run_id','attempt_id','model','prompt','case','repetition','seed','result','parser_code','response_sha256','response_file_id']}|dict(done_reason=env['done_reason'],prompt_tokens=env['prompt_eval_count'],output_tokens=env['eval_count'],num_predict=512,hit_num_predict=env['eval_count']==512,fence_present='```' in s,one_closed_fence=closed,text_before_fence=bool(before and before.strip()) if match else None,text_after_fence=bool(after and after.strip()) if match else None,syntactically_valid_after_fence_only_removal=syntax,exact_object_shape_after_fence_only_removal=sh,raw_json_syntax_valid=raw_valid,category=category,raw_json_error=error))
def aggregate(rr):
    return dict(n=len(rr),results=dict(Counter(r['result'] for r in rr)),done_reason=dict(Counter(r['done_reason'] for r in rr)),fenced=sum(r['fence_present'] for r in rr),cap=sum(r['hit_num_predict'] for r in rr),closed_fence=sum(r['one_closed_fence'] for r in rr),text_before=sum(r['text_before_fence'] is True for r in rr),text_after=sum(r['text_after_fence'] is True for r in rr),fence_only_json_syntax=sum(r['syntactically_valid_after_fence_only_removal'] is True for r in rr),fence_only_object_shape=sum(r['exact_object_shape_after_fence_only_removal'] is True for r in rr),raw_json=sum(r['raw_json_syntax_valid'] for r in rr),prompt_tokens={'min':min(r['prompt_tokens'] for r in rr),'median':statistics.median(r['prompt_tokens'] for r in rr),'max':max(r['prompt_tokens'] for r in rr),'counts':dict(sorted(Counter(r['prompt_tokens'] for r in rr).items()))},output_tokens={'min':min(r['output_tokens'] for r in rr),'median':statistics.median(r['output_tokens'] for r in rr),'max':max(r['output_tokens'] for r in rr),'counts':dict(sorted(Counter(r['output_tokens'] for r in rr).items()))})
groups={}
for fields in [('model',),('model','prompt'),('model','case'),('model','repetition'),('model','prompt','case'),('model','prompt','repetition'),('model','prompt','case','repetition')]:
    buckets=defaultdict(list)
    for r in rows:buckets[tuple(r[k] for k in fields)].append(r)
    groups['/'.join(fields)]=[dict(zip(fields,k))|aggregate(v) for k,v in sorted(buckets.items())]
summary=dict(experiment_id=1,total=aggregate(rows),by_model=groups['model'],by_model_prompt=groups['model/prompt'],cap_runs=[r for r in rows if r['hit_num_predict']],prompt_hashes=setup['prompts'],integrity=dict(frozen_sources_verified=len(setup['sources']),raw_envelopes_verified=len(rows),spool_files_verified=len(rows),request_reconstructions_hash_matched=324,request_metadata_hash_matched=324,native_reconstructions_hash_matched=216,prompt_token_mismatch_run_ids=prompt_token_mismatches),scope=dict(network_calls=0,db_connections=0,generations=0,evaluator_calls=0,experimental_parser_calls=0,rescoring=False,predictions_created=0),classification={'gemma3:27b':'MODEL FORMAT NON-COMPLIANCE','mistral-small3.2:24b':'MODEL FORMAT NON-COMPLIANCE'},interpretation_limit='Descriptive envelope/format analysis only; no hypothetical verdicts or correctness scores. Classification applies to these model/runtime/native-template combinations; causal contribution of framing is unresolved.')
summary['qualification_slots']=slot_checks
summary['inputs_sha256']={str(p.relative_to(root)):h(p.read_bytes()) for p in [base/'raw_outputs.json',base/'comparison-analysis-input.json',base/'SHA256SUMS',runtime/'context.json',runtime/'request_inventory.json',runtime/'gemma_template.txt',runtime/'mistral_template.txt',runtime/'mistral_system.txt',runtime/'source_review.json']}
for model in ('gemma3:27b','mistral-small3.2:24b'):
    rr=[r for r in rows if r['model']==model]
    assert len(rr)==108 and all(r['result']=='parser_failure' and r['done_reason']=='stop' and not r['hit_num_predict'] and r['exact_object_shape_after_fence_only_removal'] is True and not r['text_before_fence'] and not r['text_after_fence'] for r in rr)
assert Counter(r['category'] for r in rows)=={'RAW_JSON':103,'FENCED_JSON':216,'INCOMPLETE_JSON_STRING_AT_CAP':3,'EXTRA_TEXT_AFTER_JSON_AT_CAP':2}
save('ROOT_CAUSE_SUMMARY.json',summary);save('ROOT_CAUSE_RUNS.json',rows);save('ROOT_CAUSE_GROUPS.json',groups);save('ROOT_CAUSE_RECONSTRUCTION.json',reconstructed);save('ROOT_CAUSE_EXAMPLES.json',representatives)
print(json.dumps({k:summary[k] for k in ['integrity','scope']},indent=2))
for x in summary['by_model_prompt']:
    print(x['model'],x['prompt'],{k:x[k] for k in ['results','done_reason','fenced','cap','fence_only_json_syntax','fence_only_object_shape']},'tokens',[(k,x[k]['min'],x[k]['median'],x[k]['max']) for k in ['prompt_tokens','output_tokens']])
print('cap runs',[(r['run_id'],r['model'],r['prompt'],r['case'],r['repetition'],r['category']) for r in summary['cap_runs']])
