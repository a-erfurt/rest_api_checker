"""Approved comparison profile: protocol v1 section 6. No final-study metrics."""
from collections import Counter
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path

from .experiment import parser
from .experiment.request import MODELS
from .experiment.schedule import CASES, PROMPTS, Slot, comparison_schedule
from .persistence.database import json_bytes, require
from .persistence.inspection import bindings, portable, rows, status
from .persistence.importer import DEV_HASH, PROMPT_HASHES
from .persistence.repository import VERDICTS

VERSION = 'comparison-evaluation-v1'
CATEGORIES = ('c1', 'c2', 'c3')
CRITERIA = ('Score', 'Robust', 'StableCorrect', 'Reliability', 'FullCase', 'Length', 'Order')


def artifact_hash():
    root = Path(__file__).parent
    files = ('evaluation.py','persistence/inspection.py','persistence/repository.py',
             'persistence/database.py','persistence/importer.py','experiment/schedule.py',
             'experiment/request.py','experiment/encoding.py')
    return sha256(b''.join(name.encode()+b'\0'+(root/name).read_bytes()+b'\0' for name in files)).hexdigest()


def ratio(n, d):
    f = Fraction(n, d) if d else None
    return dict(numerator=n, denominator=d, value=None if f is None else f'{f.numerator}/{f.denominator}')


def exact(metric):
    return Fraction(metric['numerator'], metric['denominator'])


def rank(metrics):
    def value(p, criterion):
        return exact(metrics[p][criterion]) if criterion not in ('Length','Order') else metrics[p][criterion]
    def key(p):
        return tuple(-value(p,c) if c not in ('Length','Order') else value(p,c) for c in CRITERIA)
    ranking = sorted(metrics, key=key)
    remaining, trace = list(PROMPTS), []
    for criterion in CRITERIA:
        values = {p: value(p,criterion) for p in remaining}
        best = (min if criterion in ('Length','Order') else max)(values.values())
        survivors = [p for p in remaining if values[p] == best]
        trace.append(dict(criterion=criterion, values={p:str(v) for p,v in values.items()}, remaining=survivors))
        remaining = survivors
        if len(remaining) == 1:
            break
    return ranking, trace


def evaluate(inputs):
    """Pure engine consumes all planned, reconciled logical runs, never predictions-only."""
    runs = inputs['runs']
    slots = [Slot(r['case'], r['prompt'], r['model'], r['repetition'], r['seed'], r['run_order']) for r in runs]
    require(tuple(slots) == comparison_schedule(), 'Comparison identity/order mismatch')
    require(len({r['id'] for r in runs}) == 324, 'Duplicate logical run IDs')
    for r in runs:
        require(r['result'] in ('valid','parser_failure','technical_failure'), 'Unfinished logical run')
        require(set(r['reference']) == set(CATEGORIES) and all(v in VERDICTS for v in r['reference'].values()),
                'Incomplete reference')
        require((r['prediction'] is not None) == (r['result'] == 'valid'), 'Prediction/outcome mismatch')
        if r['prediction'] is not None:
            require(all(r['prediction'].get(c) in VERDICTS for c in CATEGORIES), 'Incomplete prediction')
    for case in CASES:
        refs = {tuple(r['reference'][c] for c in CATEGORIES) for r in runs if r['case']==case}
        require(len(refs)==1, 'Reference drift between runs')
    def correct(r, c):
        return r['result']=='valid' and r['prediction'][c]==r['reference'][c]
    metrics, diagnostics = {}, {}
    for p in PROMPTS:
        pr = [r for r in runs if r['prompt']==p]
        cells, by_model, stable = {}, {}, 0
        for m in MODELS:
            mr = [r for r in pr if r['model']==m]
            valid = [r for r in mr if r['result']=='valid']
            cells[m] = {c:ratio(sum(correct(r,c) for r in mr),36) for c in CATEGORIES}
            triples = [[r for r in mr if r['case']==case] for case in CASES]
            valid_triples = [t for t in triples if all(r['result']=='valid' for r in t)]
            stable += sum(all(correct(r,c) for r in t) for t in triples for c in CATEGORIES)
            confusion = {c:{a:{b:sum(r['reference'][c]==a and r['prediction'][c]==b for r in valid)
                                for b in sorted(VERDICTS)} for a in sorted(VERDICTS)} for c in CATEGORIES}
            disagreements = {c:ratio(sum(len({r['prediction'][c] for r in t})>1 for t in valid_triples),
                                      len(valid_triples)) for c in CATEGORIES}
            disagreements['vector'] = ratio(sum(len({tuple(r['prediction'][c] for c in CATEGORIES) for r in t})>1
                                                   for t in valid_triples),len(valid_triples))
            by_model[m] = dict(outcomes=dict(Counter(r['result'] for r in mr)),
                reliability=ratio(len(valid),36), full_case=ratio(sum(all(correct(r,c) for c in CATEGORIES) for r in mr),36),
                valid_only={c:ratio(sum(correct(r,c) for r in mr),len(valid)) for c in CATEGORIES},
                valid_coverage=ratio(len(valid),36), confusion=confusion,
                per_repetition={str(rep):{c:ratio(sum(correct(r,c) for r in mr if r['repetition']==rep),12)
                                          for c in CATEGORIES} for rep in (1,2,3)},
                stable_correct={c:ratio(sum(all(correct(r,c) for r in t) for t in triples),12) for c in CATEGORIES},
                repeat_disagreement=disagreements, valid_triple_coverage=ratio(len(valid_triples),12))
        metrics[p] = dict(Score=ratio(sum(correct(r,c) for r in pr for c in CATEGORIES),324),
            Robust=min((v for mc in cells.values() for v in mc.values()),key=exact),
            StableCorrect=ratio(stable,108), Reliability=ratio(sum(r['result']=='valid' for r in pr),108),
            FullCase=ratio(sum(all(correct(r,c) for c in CATEGORIES) for r in pr),108),
            Length=inputs['prompt_lengths'][p], Order=PROMPTS.index(p), cells=cells)
        diagnostics[p] = by_model
    ranking, trace = rank(metrics)
    return dict(format=VERSION, fabricated=inputs.get('fabricated',False), metrics=metrics, diagnostics=diagnostics,
                ranking=ranking, selected_prompt=ranking[0], selection_decided_by=trace[-1]['criterion'], tie_break_trace=trace)


def analysis_input(repo, experiment_id):
    """Caller holds a serializable transaction. Compare identities both directions."""
    state = status(repo, experiment_id)
    exp = state['experiment']
    require(exp['kind']=='comparison' and exp['finished_at'] is not None and state['pending']==0,
            'Unfinished comparison experiment')
    setup_raw = repo.file(exp['setup_file_id'])
    setup = json.loads(setup_raw)
    bound = bindings(repo, exp['dataset_id'], setup['schedule'])
    require(setup.get('bindings') == bound, 'Missing frozen bindings or configuration/reference drift')
    repo.verify_closure(setup['files'])
    require(setup['parser_sha256']==parser.artifact_hash(), 'Parser identity mismatch')
    maps = {table:{r['id']:r for r in records} for table,records in bound.items() if table!='files'}
    prompts = maps['prompts']
    lengths = {}
    for p in prompts.values():
        raw = repo.file(p['file_id'])
        require(p['name'] in PROMPT_HASHES and sha256(raw).hexdigest()==PROMPT_HASHES[p['name']], 'Prompt identity mismatch')
        lengths[p['name']] = len(raw)
    require(set(lengths)==set(PROMPTS) and len(prompts)==3, 'Prompt inventory mismatch')
    require(len(maps['models'])==3 and {m['name'] for m in maps['models'].values()}==set(MODELS), 'Model inventory mismatch')
    require(len(maps['dataset_cases'])==12, 'Dataset membership mismatch')
    records, references, evidence_ids = [], [], {exp['setup_file_id']}
    for r in state['runs']:
        member = maps['dataset_cases'][r['dataset_case_id']]
        ref = maps['reference_results'][member['reference_id']]
        source = repo.source(ref['source_file_id'],ref['source_pointer'])
        require(ref['case_id']==member['case_id'] and all(ref[c]==source[c] for c in CATEGORIES), 'Reference source drift')
        require(sha256(repo.file(ref['source_file_id'])).hexdigest()==DEV_HASH and ref['version']==1,
                'Original comparison requires released DEV reference revision; correction workflow is deferred')
        owner = repo.source(ref['source_file_id'],ref['source_pointer'].rsplit('/',1)[0])
        require(owner['case_id']==member['case_code'], 'Case/reference identity drift')
        model = maps['models'][r['model_id']]
        repo.require_d07(r['run_config_id'],model['name'])
        attempts = sorted(rows(repo,'run_attempts',run_id=r['id']),key=lambda a:a['attempt'])
        predictions = rows(repo,'predictions',run_id=r['id'])
        require(1 <= len(attempts) <= 2 and [a['attempt'] for a in attempts]==list(range(1,len(attempts)+1)), 'Attempt coverage mismatch')
        require(r['finished_at'] is not None and all(a['result'] is not None and a['finished_at'] is not None
                and a['request_file_id']==r['request_file_id'] for a in attempts), 'Unfinished/drifted attempt')
        require(attempts[-1]['result']==r['result'], 'Terminal attempt mismatch')
        if len(attempts)==2:
            require(attempts[0]['result']=='technical_failure' and
                    repo._diagnostic_root(attempts[0]['diagnostics_file_id']).get('retry_eligible') is True, 'Unqualified retry')
        if r['result']=='technical_failure':
            require(len(attempts)==2, 'Nonterminal technical failure')
        require(len(predictions)==(1 if r['result']=='valid' else 0), 'Missing/extra prediction')
        pred = predictions[0] if predictions else None
        if pred:
            require(pred['attempt_id']==attempts[-1]['id'], 'Prediction attempt mismatch')
        if r['result'] in ('valid','parser_failure'):
            envelope = json.loads(repo.file(attempts[-1]['response_file_id']))
            parsed = parser.parse(envelope['message']['content'])
            require(parsed.status==('VALID_OUTPUT' if pred else 'PARSER_FAILURE'), 'Stored parser outcome drift')
            if pred:
                require(all(pred[k]==v for k,v in parsed.prediction.items()), 'Parsed prediction drift')
        for a in attempts:
            root = repo._diagnostic_root(a['diagnostics_file_id'])
            require(root.get('parser_sha256')==setup['parser_sha256'] and root.get('run_id')==r['id']
                    and root.get('attempt_id')==a['id'] and root.get('request_sha256')==sha256(repo.file(a['request_file_id'])).hexdigest(),
                    'Attempt diagnostic identity drift')
        for row in [r,*attempts]:
            evidence_ids.update(v for k,v in row.items() if k.endswith('file_id') and v is not None)
        records.append(dict(**r, case=member['case_code'], model=model['name'], prompt=prompts[r['prompt_id']]['name'],
                            reference={c:ref[c] for c in CATEGORIES}, prediction=pred, attempts=attempts))
        references.append(dict(run_id=r['id'],reference_id=ref['id'],version=ref['version'],case_id=ref['case_id']))
    files = {f['file_id']:f for f in [*setup['files'],*bound['files']]}
    # Follow only repository-owned diagnostic links, never arbitrary provider
    # JSON fields. Other experiments and previous reports are not analysis input.
    pending = list(evidence_ids | set(files))
    visited = set()
    while pending:
        file_id = pending.pop()
        if file_id in visited:
            continue
        visited.add(file_id)
        raw = repo.file(file_id)
        row = repo._row('files',file_id)
        files[file_id] = dict(file_id=file_id,sha256=sha256(raw).hexdigest(),name=row['name'])
        if row['name'] in ('attempt-diagnostics.json','diagnostic-successor.json'):
            value = json.loads(raw)
            if value.get('format')=='diagnostic-successor-v1':
                if value['previous_file_id'] is not None:
                    pending.append(value['previous_file_id'])
                repo.verify_closure(value['evidence']['files'])
                pending.extend(f['file_id'] for f in value['evidence']['files'])
            else:
                if value.get('preceding_evidence'):
                    repo.verify_closure([value['preceding_evidence']])
                    pending.append(value['preceding_evidence']['file_id'])
                provenance = value.get('transport',{}).get('request_provenance_file_id')
                if provenance is not None:
                    pending.append(provenance)
    relational = portable(dict(runs=records,bindings=bound,references=references))
    return portable(dict(format='comparison-analysis-input-v1',experiment_id=experiment_id,experiment=exp,
        relational_sha256=sha256(json_bytes(relational)).hexdigest(),
        setup_sha256=sha256(setup_raw).hexdigest(),setup=setup,bindings=bound,references=references,
        files=[files[i] for i in sorted(files)],runs=records,prompt_lengths=lengths,fabricated=state['fabricated'],
        evaluator_version=VERSION,evaluator_sha256=artifact_hash()))


def create_report(repo, experiment_id):
    require(repo._depth==0, 'Report requires its own snapshot transaction')
    repo.cn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
    try:
        with repo.transaction():
            inputs = analysis_input(repo,experiment_id)
            # Persist the immutable input first. Computation reads those bytes.
            input_id = repo.archive('comparison-analysis-input.json',json_bytes(inputs))
            raw = repo.file(input_id)
            report = evaluate(json.loads(raw))
            report.update(input_sha256=sha256(raw).hexdigest(),experiment_id=experiment_id,
                          source=dict(setup_sha256=inputs['setup_sha256'],bindings=inputs['bindings'],
                                      references=inputs['references'],files=inputs['files']),
                          evaluator_sha256=inputs['evaluator_sha256'])
            report['runs'] = [dict(id=r['id'],case=r['case'],model=r['model'],prompt=r['prompt'],
                repetition=r['repetition'],seed=r['seed'],run_order=r['run_order'],result=r['result'],
                reference=r['reference'],prediction=None if r['prediction'] is None else {c:r['prediction'][c] for c in CATEGORIES},
                correctness={c:r['prediction'][c]==r['reference'][c] if r['prediction'] else False for c in CATEGORIES})
                for r in inputs['runs']]
            file_id = repo.archive('comparison-evaluation-report.json',json_bytes(report))
            report_id = repo.report(experiment_id=experiment_id,input_file_id=input_id,file_id=file_id,
                                    code_version=VERSION+':'+inputs['evaluator_sha256'])
        return report_id, report
    finally:
        repo.cn.execute('SET TRANSACTION ISOLATION LEVEL READ COMMITTED')
        repo.cn.commit()
