import json,hashlib
from pathlib import Path
from contextlib import closing
from rest_api_checker import evaluation,freeze
from rest_api_checker.persistence.database import connect,read_settings,json_bytes
from rest_api_checker.persistence.repository import Repository,TABLES
from rest_api_checker.persistence.inspection import rows,portable
p=Path('/tmp/rac_exp1_analysis_20260926');before=json.loads((p/'db_before.json').read_bytes())
h=lambda b:hashlib.sha256(b).hexdigest()
with closing(connect(read_settings(Path.home()/'.config/rest-api-checker/application-credentials.env'),'rest_api_checker')) as cn:
 repo=Repository(cn);cn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
 reports=rows(repo,'evaluation_reports');assert len(reports)==1 and reports[0]['experiment_id']==1
 rr=reports[0];raw=repo.file(rr['file_id']);inp=repo.file(rr['input_file_id'])
 assert json.loads(raw)==json.loads((p/'evaluation_result.json').read_bytes())['report']
 assert inp==(p/'analysis_input.json').read_bytes()
 (p/'comparison-evaluation-report.json').write_bytes(raw);(p/'comparison-analysis-input.json').write_bytes(inp)
 current={}
 for t in TABLES:
  if t=='files':
   cur=cn.execute('SELECT id,name,sha256,size_bytes FROM dbo.files ORDER BY id');data=[dict(zip([d[0] for d in cur.description],r)) for r in cur.fetchall()]
   old=[r for r in data if r['id']<=before[t]['count']];assert h(json_bytes(old))==before[t]['sha256']
  else:data=portable(rows(repo,t))
  current[t]={'count':len(data),'sha256':h(json_bytes(data))}
  if t not in ('files','evaluation_reports'):assert current[t]==before[t],t
 assert current['files']['count']==before['files']['count']+2
 freeze.check_sources(json.loads(inp)['setup'],Path.cwd(),Path.cwd().parent/'bachelor_rest_api_checker')
 cn.rollback()
 result={'report_metadata':rr,'report_sha256':h(raw),'input_sha256':h(inp),'db_after':current,'protected_tables_unchanged':True,'existing_file_records_unchanged':True,'source_hashes_unchanged':True,'new_archive_files':2,'new_evaluation_reports':1}
 (p/'postcheck.json').write_bytes(json_bytes(portable(result)))
 print(json.dumps(portable(result),indent=2))
