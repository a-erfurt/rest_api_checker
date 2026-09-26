import sys,json,hashlib,base64,subprocess
from pathlib import Path
from collections import Counter
from contextlib import closing
from rest_api_checker import evaluation,freeze
from rest_api_checker.experiment import parser
from rest_api_checker.persistence import spool
from rest_api_checker.persistence.database import connect,read_settings,json_bytes
from rest_api_checker.persistence.repository import Repository,TABLES
from rest_api_checker.persistence.inspection import rows,portable,status
root=Path('/Users/aerfurt/University/Bachelor/rest_api_checker')
research=root.parent/'bachelor_rest_api_checker'
out=Path(sys.argv[1]);out.mkdir(exist_ok=True)
def save(n,v): (out/n).write_bytes(json_bytes(portable(v)))
def h(b):return hashlib.sha256(b).hexdigest()
with closing(connect(read_settings(Path.home()/'.config/rest-api-checker/application-credentials.env'),'rest_api_checker')) as cn:
 repo=Repository(cn)
 cn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
 inputs=evaluation.analysis_input(repo,1)
 setup=inputs['setup'];candidate_raw=repo.file(setup['author_candidate_file_id']);approval_raw=repo.file(setup['author_acceptance_file_id'])
 candidate=json.loads(candidate_raw);approval=json.loads(approval_raw)
 freeze.require_acceptance(candidate_raw,approval)
 assert h(candidate_raw)==setup['author_candidate_sha256'] and h(approval_raw)==setup['author_acceptance_sha256']
 assert candidate['evaluator']['sha256']==evaluation.artifact_hash()
 freeze.check_sources(candidate,root,research)
 assert candidate['implementation_commit']==subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
 for k,v in candidate.items():
  if k not in ('files','gate_b_complete'): assert setup[k]==v,k
 save('analysis_input.json',inputs)
 save('acceptance.json',approval)
 save('status.json',status(repo,1))
 save('reports_before.json',rows(repo,'evaluation_reports'))
 db={}
 for t in TABLES:
  if t=='files':
   rr=[dict(zip([d[0] for d in cur.description],r)) for cur in [cn.execute('SELECT id,name,sha256,size_bytes FROM dbo.files ORDER BY id')] for r in cur.fetchall()]
  else: rr=portable(rows(repo,t))
  db[t]={'count':len(rr),'sha256':h(json_bytes(rr))}
 save('db_before.json',db)
 rawrows=[]
 spool_map={}
 for p in sorted((root.parent/'rest_api_checker_spool/prompt_comparison_exp1').iterdir()):
  raw,v,response=spool.read(p);key=(v['run_id'],v['attempt_id']);assert key not in spool_map
  spool_map[key]=(p,raw,v,response)
 for r in inputs['runs']:
  for a in r['attempts']:
   p,spraw,v,response=spool_map.pop((r['id'],a['id']))
   archived=repo.file(a['response_file_id']);assert response==archived
   assert v['request_sha256']==h(repo.file(a['request_file_id'])) and v['setup_sha256']==inputs['setup_sha256']
   env=json.loads(response);parsed=parser.parse(env['message']['content'])
   diag=repo._diagnostic_root(a['diagnostics_file_id'])
   rawrows.append(dict(run_id=r['id'],attempt_id=a['id'],case=r['case'],model=r['model'],prompt=r['prompt'],repetition=r['repetition'],seed=r['seed'],result=r['result'],response_file_id=a['response_file_id'],response_sha256=h(response),response_base64=base64.b64encode(response).decode(),content=env['message']['content'],provider={k:v for k,v in env.items() if k!='message'},thinking=env['message'].get('thinking'),parser_code=parsed.code,parser_path=parsed.path,diagnostic=diag,spool_path=str(p),spool_sha256=h(spraw)))
 assert not spool_map
 save('raw_outputs.json',rawrows)
 console_path=root.parent/'rest_api_checker_spool/prompt_comparison_exp1_console.log'
 console=console_path.read_bytes();last=json.loads(console.decode().splitlines()[-1]);assert last['exit_code']==0 and last['status']=='COMPLETED'
 assert last['state']==status(repo,1)
 save('console_summary.json',{k:v for k,v in last.items() if k!='state'}|{'state':{k:v for k,v in last['state'].items() if k!='runs'},'path':str(console_path),'sha256':h(console)})
 cn.rollback()
print(json.dumps({'rows':len(rawrows),'outcomes':dict(Counter(r['result'] for r in rawrows)),'parser_codes':dict(Counter(r['parser_code'] for r in rawrows)),'db':db,'console':{k:v for k,v in last.items() if k!='state'}},indent=2))
