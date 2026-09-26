"""Native tokenization of fabricated render only; no generation."""
import json
import re
import sys
import urllib.request
from capture import OUT,save
short=sys.argv[1]
line=json.loads((OUT/(short+'_runner.json')).read_bytes())[-1]
port=re.search(r'--port (\d+)',line)[1]
render=json.loads((OUT/(short+'_diagnostic_render.json')).read_bytes())['_debug_info']['rendered_template']
rows=[]
for add in (False,True):
 body=json.dumps({'content':render,'add_special':add,'parse_special':True}).encode()
 with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:'+port+'/tokenize',data=body,headers={'Content-Type':'application/json'})) as r:
  tokens=json.load(r)['tokens']
 rows.append(dict(add_special=add,parse_special=True,count=len(tokens),tokens=tokens))
for endpoint in ('props','slots'):
 with urllib.request.urlopen('http://127.0.0.1:'+port+'/'+endpoint) as r: save(short+'_'+endpoint+'.json',json.load(r))
save(short+'_token_parity.json',rows)
print(short, [(r['add_special'],r['count']) for r in rows])
