"""Offline replay: reads evidence only; no DB, provider, output repair, or model calls.
Usage: ROOT/.venv/bin/python reproduce_analysis.py NEW_OUTPUT_DIRECTORY
Requires the frozen installed rest_api_checker implementation.
"""
import base64
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import sys
from rest_api_checker import evaluation
from rest_api_checker.experiment import parser

base=Path(__file__).resolve().parent
out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False)
def load(name):return json.loads((base/name).read_bytes())
def save(name,value):
 with (out/name).open('x') as f:json.dump(value,f,indent=2,sort_keys=True);f.write('\n')
inputs=load('comparison-analysis-input.json');report=load('comparison-evaluation-report.json');raw=load('raw_outputs.json')
assert evaluation.artifact_hash()==inputs['evaluator_sha256']==inputs['setup']['evaluator']['sha256']
assert parser.artifact_hash()==inputs['setup']['parser_sha256']
assert sha256((base/'comparison-analysis-input.json').read_bytes()).hexdigest()==report['input_sha256']
replayed=evaluation.evaluate(inputs)
assert all(report[k]==v for k,v in replayed.items())
by_id={r['id']:r for r in inputs['runs']};assert len(raw)==len(by_id)==324
members={x['id']:x for x in inputs['bindings']['dataset_cases']}
cases={x['id']:x for x in inputs['bindings']['test_cases']}
ops={x['id']:x for x in inputs['bindings']['api_operations']}
fail=[]
for r in raw:
 run=by_id[r['run_id']];response=base64.b64decode(r['response_base64'],validate=True)
 assert sha256(response).hexdigest()==r['response_sha256']
 env=json.loads(response);assert env['message']['content']==r['content']
 parsed=parser.parse(r['content'])
 assert parsed.code==r['parser_code']==r['diagnostic']['parser']['code']
 assert parsed.status==('VALID_OUTPUT' if run['result']=='valid' else 'PARSER_FAILURE')
 if parsed.prediction:assert all(run['prediction'][k]==v for k,v in parsed.prediction.items())
 case=cases[members[run['dataset_case_id']]['case_id']]
 r.update(family_id=case['family_id'],origin=case['origin'],operation=ops[case['operation_id']]['path_template'])
 if r['result']!='parser_failure':continue
 s=r['content']
 try:json.loads(s)
 except json.JSONDecodeError as e:err=dict(message=e.msg,offset=e.pos,line=e.lineno,column=e.colno)
 else:raise AssertionError('Unexpected accepted JSON grammar')
 if s.startswith('```json\n') and s.endswith('\n```') and s.count('```')==2:category='MARKDOWN_FENCED_FINAL_CONTENT'
 elif err['message']=='Unterminated string starting at':category='UNTERMINATED_JSON_STRING_AT_TOKEN_LIMIT'
 elif err['message']=='Extra data':category='EXTRA_PROSE_AFTER_JSON_AT_TOKEN_LIMIT'
 else:raise AssertionError('Unclassified failure')
 # Only the unmodified complete string is inspected. No prefix/body is parsed or scored.
 assert r['diagnostic']['final_content']==s and r['diagnostic']['retry_eligible'] is False
 if category!='MARKDOWN_FENCED_FINAL_CONTENT':assert env['done_reason']=='length' and env['eval_count']==512
 fail.append({k:r[k] for k in ['run_id','attempt_id','model','prompt','case','repetition','response_file_id','response_sha256','spool_path','spool_sha256']}|dict(category=category,parser_code=parsed.code,json_error=err,done_reason=env['done_reason'],eval_count=env['eval_count']))
groups={}
fields_list=[('model',),('prompt',),('case',),('repetition',),('operation',),('origin',),('family_id',),('model','prompt'),('model','case'),('prompt','case'),('model','repetition'),('prompt','repetition'),('model','prompt','repetition'),('model','prompt','case'),('model','prompt','case','repetition')]
for fields in fields_list:
 d=defaultdict(Counter)
 for r in raw:d[tuple(r[k] for k in fields)][r['result']]+=1
 groups['/'.join(fields)]=[dict(zip(fields,k))|{t:v[t] for t in ['valid','parser_failure','technical_failure']}|dict(denominator=sum(v.values())) for k,v in sorted(d.items())]
assert Counter(x['category'] for x in fail)=={'MARKDOWN_FENCED_FINAL_CONTENT':216,'UNTERMINATED_JSON_STRING_AT_TOKEN_LIMIT':3,'EXTRA_PROSE_AFTER_JSON_AT_TOKEN_LIMIT':2}
save('failure_classification.json',fail);save('distributions.json',groups);save('replayed_evaluation.json',replayed)
save('replay_checks.json',dict(raw_envelopes_verified=324,parser_outcomes_verified=324,failure_descriptions_verified=221,frozen_evaluator_reproduced=True,ranking=report['ranking'],model_calls=0,db_writes=0))
print('PASS: 324 raw envelopes/outcomes, 221 failure descriptions, frozen metrics and ranking reproduced offline.')
