"""Exact native render/token-count-only measurement; no completion call on study data."""
from datetime import datetime
import json
import re
import subprocess
import urllib.request
from capture import ROOT, RESEARCH, OUT, api, save, digest
from rest_api_checker.persistence.importer import load_development
from rest_api_checker.experiment import renderer, request, schedule

identities=json.loads((OUT/'identities.json').read_bytes())
manifest,closure=load_development(ROOT/'artifacts/development_dataset_v1',ROOT/'docs/development_dataset_v1_release.json',RESEARCH)
candidates=json.loads((RESEARCH/'03_research_design/prompt_candidates_v1/candidate_manifest_v1.json').read_bytes())
prompts={p['id']:(RESEARCH/p['path']).read_bytes() for p in candidates['candidates']}
rendered={}
for c in manifest['cases']:
 contract=manifest['sources'][manifest['contracts'][c['api']]]['path']; body=c['body']['path']
 rendered[c['case_id']]=renderer.render(renderer.Evidence(closure[contract],c['operation']['method'],c['operation']['path'],c['status'],c['content_type'],closure[body]),contract_identity=contract,body_identity=body)
rows=[]
for model,short in zip(request.MODELS,('qwen','gemma','mistral')):
 identity=next(m for m in identities if m['name']==model)
 parity=json.loads((OUT/(short+'_token_parity.json')).read_bytes())
 diagnostic=json.loads((OUT/(short+'_diagnostic_result.json')).read_bytes())
 assert next(p for p in parity if p['add_special'])['count']==diagnostic['envelope']['prompt_eval_count']
 cache={}
 for slot in [s for s in schedule.comparison_schedule() if s.model==model]:
  req=request.build_request(rendered[slot.case],prompt_name=slot.prompt,prompt=prompts[slot.prompt],model=model,model_digest=identity['digest'],repetition=slot.repetition)
  request.validate_request(req)
  key=(slot.case,slot.prompt)
  if key not in cache:
   payload=json.loads(req.body)
   # The ONLY chat call on study inputs is the source-reviewed render-only path.
   debug=api('/api/chat',{**payload,'_debug_render_only':True,'truncate':False})
   assert not debug.get('done') and not debug.get('eval_count') and not debug.get('message',{}).get('content')
   text=debug['_debug_info']['rendered_template']
   assert not debug['_debug_info'].get('image_count')
   lines=subprocess.check_output(['ps','-axo','args'],text=True).splitlines()
   blob=next(l['digest'] for l in identity['layers'] if l['mediaType']=='application/vnd.ollama.image.model').replace(':','-')
   runners=[l for l in lines if '/llama-server --model ' in l and blob in l]
   assert len(runners)==1
   port=re.search(r'--port (\d+)',runners[0])[1]
   body=json.dumps(dict(content=text,add_special=True,parse_special=True)).encode()
   with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:'+port+'/tokenize',data=body,headers={'Content-Type':'application/json'}),timeout=30) as r:
    tokens=json.load(r)['tokens']
   cache[key]=dict(input_tokens=len(tokens),total_tokens=len(tokens)+512,margin=32768-len(tokens)-512,rendered_sha256=digest(text.encode()),tokens_sha256=digest(json.dumps(tokens,separators=(',',':')).encode()),model_digest=identity['digest'],template_sha256=identity['template_sha256'])
  rows.append(dict(case=slot.case,prompt=slot.prompt,model=model,repetition=slot.repetition,run_order=slot.run_order,request_sha256=digest(req.body),**cache[key]))
 save('context_partial.json',rows)
 print(model,'measured',len(cache),'max',max(v['input_tokens'] for v in cache.values()),flush=True)
save('context.json',dict(captured_at=datetime.now().astimezone().isoformat(),method='Ollama 0.34.4 _debug_render_only + same live llama-server /tokenize add_special=true parse_special=true',study_generation_calls=0,render_only_calls=108,tokenize_calls=108,seed_invariant_rendering=True,rows=rows))
(OUT/'context_partial.json').unlink()
