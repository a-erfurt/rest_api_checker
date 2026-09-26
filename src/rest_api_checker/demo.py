"""FABRICATED / TEST DATA only. Refuses unmarked or non-disposable SQL databases."""
from dataclasses import asdict
import json
import re
import time

from .experiment import parser, renderer, request, schedule
from .experiment.encoding import digest, encode
from .experiment.provider import Receipt
from .persistence.database import require, utc_now
from .persistence.importer import import_development, import_prompts
from .persistence.repository import D07


def require_isolation(repo):
    name = repo.cn.execute('SELECT DB_NAME()').fetchval()
    require(re.fullmatch(r'rac_test_[0-9a-f]{32}',name), 'FABRICATED demo requires a disposable rac_test_<uuid> database')
    require(repo.cn.execute("SELECT CAST(value AS nvarchar(20)) FROM sys.extended_properties WHERE class=0 AND name=N'rest_api_checker_disposable'").fetchval()=='v1',
            'FABRICATED demo requires disposable database marker')
    repo.cn.commit()


def plan(repo, root, research):
    require_isolation(repo)
    dev = import_development(repo,root/'artifacts/development_dataset_v1',root/'docs/development_dataset_v1_release.json',research)
    imported = import_prompts(repo,research)
    prompts = imported['prompt_ids']
    members = dict(zip(schedule.CASES,dev['membership_ids']))
    metadata = repo.archive('FABRICATED-model-metadata.json',b'{"fabricated":true}')
    models = {m:repo.model(name=m,family='FABRICATED',parameters_b=None,quantization='Q4_K_M',context_length=32768,
        digest='sha256:'+str(i+1)*64,architecture='FABRICATED',metadata_file_id=metadata) for i,m in enumerate(request.MODELS)}
    configs = {m:repo.configuration(think=False if m==request.MODELS[0] else None,**D07) for m in request.MODELS}
    manifest = json.loads(repo.file(dev['files']['manifest.json']))
    rendered = {}
    for c in manifest['cases']:
        contract = manifest['sources'][manifest['contracts'][c['api']]]
        rendered[c['case_id']] = renderer.render(renderer.Evidence(repo.file(dev['files'][contract['path']]),
            c['operation']['method'],c['operation']['path'],c['status'],c['content_type'],repo.file(dev['files'][c['body']['path']])),
            contract_identity=contract['path'],body_identity=c['body']['path'])
    proofs = {}
    for s in schedule.comparison_schedule():
        model = repo._row('models',models[s.model])
        req = request.build_request(rendered[s.case],prompt_name=s.prompt,
            prompt=repo.file(repo._row('prompts',prompts[s.prompt])['file_id']),model=s.model,
            model_digest=model['digest'],repetition=s.repetition)
        proofs[str(s.run_order)] = asdict(request.ContextProof(digest(req.body),model['digest'],'b'*64,'c'*64,10000))
    file_ids = set(dev['files'].values()) | set(imported['files'].values()) | {metadata}
    setup = dict(parser_sha256=parser.artifact_hash(),renderer_sha256=renderer.artifact_hash(),
        fabricated=True,gate_b_complete=False,context_proofs=proofs,
        files=[dict(file_id=i,sha256=digest(repo.file(i))) for i in sorted(file_ids)])
    return schedule.persist_comparison(repo,name='FABRICATED / TEST DATA — CLI demo',dataset_id=dev['dataset_id'],
        memberships=members,prompts=prompts,models=models,configs=configs,setup=setup)


class FabricatedClient:
    """Fixed answers independent of references. Scenario keyed by persisted run order."""
    def __init__(self, repo, *, delay=0):
        require_isolation(repo)
        self.repo, self.delay, self.current = repo, delay, None
        self.calls = 0

    def event(self, event):
        if event['event']=='current':
            self.current = event['current']

    def send(self, req, *, on_start):
        self.calls += 1
        started = utc_now()
        on_start(started)
        if self.delay:
            time.sleep(self.delay)
        # No SQL calls during provider I/O. run_id is from the scheduler event.
        order = self.current['order'] if 'order' in self.current else self.orders[self.current['run_id']]
        technical = order==3 or (order==2 and self.current['attempt']==1)
        content = '{' if order==1 else encode({c:dict(verdict='PASS',reason='FABRICATED fixed answer; no inference')
                                              for c in ('c1','c2','c3')}).decode()
        raw = b'FABRICATED transport interruption' if technical else encode(dict(done=True,done_reason='stop',
                       message=dict(role='assistant',content=content),prompt_eval_count=10,eval_count=10))
        return Receipt(raw,dict(complete=not technical,error_kind='transport' if technical else None,
            error_message='FABRICATED isolated connection reset' if technical else None,
            http_status=None if technical else 200,duration_ms=1,headers=[]),started,utc_now())


def client_for(repo, experiment_id, delay=0):
    from .persistence.inspection import status
    require_isolation(repo)
    state = status(repo,experiment_id)
    require(state['fabricated'] and state['experiment']['name'].startswith('FABRICATED'), 'Not a fabricated experiment')
    client = FabricatedClient(repo,delay=delay)
    client.orders = {r['id']:r['run_order'] for r in state['runs']}
    repo.cn.commit()
    return client
