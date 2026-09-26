"""Persisted D11 input closure and immutable report publication; no inference."""
import json

from . import evaluation as comparison, sensitivity_evaluation as se, sensitivity_freeze as sf
from . import sensitivity_execution as sx
from .experiment import parser
from .experiment.encoding import digest, encode
from .persistence.database import require
from .persistence.inspection import rows, status, bindings, portable


def analysis_input(repo,experiment_id):
    state=status(repo,experiment_id);exp=state['experiment']
    require(exp['kind']=='sensitivity' and exp['finished_at'] is not None and state['pending']==0,
            'Incomplete sensitivity experiment')
    setup_raw=repo.file(exp['setup_file_id']);setup=json.loads(setup_raw)
    raw=repo.file(setup['author_candidate_file_id']);approval=repo.file(setup['author_acceptance_file_id'])
    candidate=json.loads(raw)
    sx.require_persisted(repo,experiment_id,raw,approval,candidate,finish_read=False)
    require(candidate['evaluator']==dict(version=se.VERSION,sha256=se.artifact_hash()),'Unexpected evaluator schema/identity')
    require(setup['parser_sha256']==parser.artifact_hash(),'Parser schema drift')
    base=candidate['baseline'];baseline=comparison.analysis_input(repo,base['experiment_id'])
    require(baseline['setup_sha256']==base['setup_sha256'],'Baseline setup mismatch')
    require(baseline['setup']['author_candidate_sha256']==base['candidate_sha256']
        and baseline['setup']['author_acceptance_sha256']==base['acceptance_sha256'],'Baseline acceptance mismatch')
    report=repo._row('evaluation_reports',base['report']['id'])
    require(portable(report)==base['report'] and digest(repo.file(report['file_id']))==base['report_sha256'],
            'Baseline report drift')
    report_value=json.loads(repo.file(report['file_id']))
    require(report['experiment_id']==base['experiment_id'] and report_value['experiment_id']==base['experiment_id']
        and report_value['format']==comparison.VERSION and report_value['selected_prompt']=='P2',
        'Wrong baseline prompt/evaluation schema/experiment')
    bound=bindings(repo,exp['dataset_id'],setup['schedule'])
    # Exact original dataset/reference/model/config rows; only the prompt differs.
    for table in ('datasets','dataset_cases','test_cases','reference_results','models','run_configs'):
        if table in bound:
            require(bound[table]==baseline['bindings'][table],'Baseline/sensitivity binding mismatch: '+table)
    maps={k:{r['id']:r for r in v} for k,v in bound.items() if k!='files'}
    records=[];files={f['file_id']:f for f in [*setup['files'],*bound['files'],*baseline['files']]}
    def retain(identity):
        if identity is not None:
            value=repo.file(identity);files[identity]=dict(file_id=identity,sha256=digest(value))
    retain(exp['setup_file_id'])
    for r in state['runs']:
        member=maps['dataset_cases'][r['dataset_case_id']];ref=maps['reference_results'][member['reference_id']]
        model=maps['models'][r['model_id']];repo.require_d07(r['run_config_id'],model['name'])
        attempts=sorted(rows(repo,'run_attempts',run_id=r['id']),key=lambda a:a['attempt'])
        predictions=rows(repo,'predictions',run_id=r['id'])
        require(1<=len(attempts)<=2 and [a['attempt'] for a in attempts]==list(range(1,len(attempts)+1)),
                'Missing/duplicate physical attempts')
        require(r['result'] in se.OUTCOMES and r['finished_at'] is not None and all(a['result'] is not None
            and a['finished_at'] is not None and a['request_file_id']==r['request_file_id'] for a in attempts),
            'Unresolved technical hold or attempt drift')
        require(attempts[-1]['result']==r['result'],'Terminal attempt mismatch')
        if len(attempts)==2:
            require(attempts[0]['result']=='technical_failure' and
                repo._diagnostic_root(attempts[0]['diagnostics_file_id']).get('retry_eligible') is True,'Unqualified retry')
        if r['result']=='technical_failure':require(len(attempts)==2,'Unfinished technical failure')
        require(len(predictions)==(1 if r['result']=='valid' else 0),'Missing/extra prediction')
        prediction=predictions[0] if predictions else None
        if prediction:require(prediction['attempt_id']==attempts[-1]['id'],'Prediction attempt drift')
        if r['result'] in ('valid','parser_failure'):
            parsed=parser.parse(json.loads(repo.file(attempts[-1]['response_file_id']))['message']['content'])
            require(parsed.status==('VALID_OUTPUT' if prediction else 'PARSER_FAILURE'),'Persisted parser outcome drift')
            if prediction:require(all(prediction[k]==v for k,v in parsed.prediction.items()),'Persisted prediction drift')
        expected=candidate['request_inventory'][r['run_order']-1]
        require(digest(repo.file(r['request_file_id']))==expected['request_sha256'],'Persisted request drift')
        for a in attempts:
            diagnostic=repo._diagnostic_root(a['diagnostics_file_id'])
            require(diagnostic.get('parser_sha256')==setup['parser_sha256'] and diagnostic.get('run_id')==r['id']
                and diagnostic.get('attempt_id')==a['id'] and diagnostic.get('request_sha256')==expected['request_sha256'],
                'Attempt diagnostic binding mismatch')
        for record in (r,*attempts):
            for key,value in record.items():
                if key.endswith('file_id'):retain(value)
        records.append(dict(**r,case=member['case_code'],model=model['name'],prompt=sf.PROMPT,
            reference={c:ref[c] for c in se.CATEGORIES},prediction=prediction,attempts=attempts))
    baseline_runs=[r for r in baseline['runs'] if r['prompt']=='P2']
    require([r['id'] for r in baseline_runs]==[r['baseline_run_id'] for r in candidate['request_inventory']],
            'Wrong matched baseline runs')
    # Close retained diagnostic chains, including evidence-only crash recovery
    # predecessors. Follow repository-owned links only, never provider JSON.
    pending=list(files);visited=set()
    while pending:
        identity=pending.pop()
        if identity in visited:continue
        visited.add(identity)
        row=repo._row('files',identity)
        if row['name'] not in ('attempt-diagnostics.json','diagnostic-successor.json'):continue
        value=json.loads(repo.file(identity));linked=[]
        if value.get('format')=='diagnostic-successor-v1':
            if value['previous_file_id'] is not None:linked.append(value['previous_file_id'])
            repo.verify_closure(value['evidence']['files'])
            linked.extend(f['file_id'] for f in value['evidence']['files'])
        else:
            if value.get('preceding_evidence'):
                repo.verify_closure([value['preceding_evidence']]);linked.append(value['preceding_evidence']['file_id'])
            provenance=value.get('transport',{}).get('request_provenance_file_id')
            if provenance is not None:linked.append(provenance)
        for i in linked:retain(i);pending.append(i)
    result=portable(dict(format='sensitivity-d11-analysis-input-v1',experiment_id=experiment_id,
        setup_sha256=digest(setup_raw),candidate_sha256=digest(raw),baseline_binding=base,bindings=bound,
        baseline_runs=baseline_runs,sensitivity_runs=records,prompt_hashes={'P2':sf.PARENT_SHA,sf.PROMPT:sf.SHA},
        fabricated=state['fabricated'],files=[files[i] for i in sorted(files)],
        references=[dict(run_id=r['id'],reference_id=maps['dataset_cases'][r['dataset_case_id']]['reference_id']) for r in records],
        evaluator_version=se.VERSION,evaluator_sha256=se.artifact_hash()))
    se.validate(baseline_runs,'P2');se.validate(records,sf.PROMPT)
    require(all(b['reference']==w['reference'] for b,w in zip(baseline_runs,records)),'Reference mismatch')
    return result


def create_report(repo,experiment_id):
    require(repo._depth==0,'Report requires its own snapshot transaction')
    repo.cn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
    try:
        with repo.transaction():
            inputs=analysis_input(repo,experiment_id)
            input_id=repo.archive('sensitivity-d11-analysis-input.json',encode(inputs));raw=repo.file(input_id)
            report=se.evaluate(json.loads(raw))
            report.update(experiment_id=experiment_id,input_sha256=digest(raw),evaluator_sha256=se.artifact_hash(),
                          baseline_binding=inputs['baseline_binding'])
            file_id=repo.archive('sensitivity-d11-evaluation-report.json',encode(report))
            report_id=repo.report(experiment_id=experiment_id,input_file_id=input_id,file_id=file_id,
                                 code_version=se.VERSION+':'+se.artifact_hash(),
                                 baseline_report_id=inputs['baseline_binding']['report']['id'])
        return report_id,report
    finally:
        repo.cn.execute('SET TRANSACTION ISOLATION LEVEL READ COMMITTED');repo.cn.commit()
