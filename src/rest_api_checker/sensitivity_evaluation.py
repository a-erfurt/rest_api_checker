"""Protocol v1 §9/D11 paired description. No ranking, threshold or prompt selection."""
from collections import Counter
from pathlib import Path
import json

from .evaluation import CATEGORIES, ratio
from .experiment import parser
from .experiment.encoding import digest, encode
from .experiment.request import MODELS, SEEDS
from .experiment.schedule import CASES, comparison_schedule
from .persistence.database import require
from .persistence.repository import VERDICTS
from . import sensitivity_freeze as sf

VERSION = 'sensitivity-d11-evaluation-v1'
OUTCOMES = ('valid', 'parser_failure', 'technical_failure')


def artifact_hash():
    root = Path(__file__).parent
    names = ('sensitivity_evaluation.py', 'sensitivity_analysis.py', 'evaluation.py',
             'experiment/parser.py', 'experiment/encoding.py')
    return digest(b''.join(n.encode()+b'\0'+(root/n).read_bytes()+b'\0' for n in names))


def validate(runs, prompt):
    expected = [(s.case,s.model,s.repetition,s.seed) for s in comparison_schedule() if s.prompt=='P2']
    require(len(runs)==108 and len({r['id'] for r in runs})==108, 'Missing/duplicate logical runs')
    require([(r['case'],r['model'],r['repetition'],r['seed']) for r in runs]==expected,
            'Paired schedule/repetition/seed mismatch')
    orders = [s.run_order for s in comparison_schedule() if s.prompt=='P2'] if prompt=='P2' else list(range(1,109))
    require([r['run_order'] for r in runs]==orders,'Logical run order mismatch')
    for r in runs:
        require(r['prompt']==prompt and r['result'] in OUTCOMES, 'Wrong prompt or unfinished logical run')
        require(set(r['reference'])==set(CATEGORIES) and all(v in VERDICTS for v in r['reference'].values()),
                'Incomplete reference')
        require((r['prediction'] is not None)==(r['result']=='valid'), 'Prediction/outcome mismatch')
        if r['prediction'] is not None:
            require(all(r['prediction'].get(c) in VERDICTS for c in CATEGORIES), 'Invalid prediction')
    for case in CASES:
        require(len({tuple(r['reference'][c] for c in CATEGORIES) for r in runs if r['case']==case})==1,
                'Reference drift between repetitions/models')


def correct(r, c):
    return r['result']=='valid' and r['prediction'][c]==r['reference'][c]


def outcomes(runs):
    counts = Counter(r['result'] for r in runs)
    return {k:ratio(counts[k],len(runs)) for k in OUTCOMES}


def describe(runs):
    models = {}
    stable = 0
    for model in MODELS:
        mr = [r for r in runs if r['model']==model]
        triples = [[r for r in mr if r['case']==case] for case in CASES]
        valid = [t for t in triples if all(r['result']=='valid' for r in t)]
        stability = {c:ratio(sum(all(correct(r,c) for r in t) for t in triples),12) for c in CATEGORIES}
        stable += sum(s['numerator'] for s in stability.values())
        disagreement = {c:ratio(sum(len({r['prediction'][c] for r in t})>1 for t in valid),len(valid))
                        for c in CATEGORIES}
        disagreement['vector'] = ratio(sum(len({tuple(r['prediction'][c] for c in CATEGORIES) for r in t})>1
                                                for t in valid),len(valid))
        models[model] = dict(
            categories={c:ratio(sum(correct(r,c) for r in mr),36) for c in CATEGORIES},
            ModelCorrect=ratio(sum(correct(r,c) for r in mr for c in CATEGORIES),108),
            StableCorrect=ratio(sum(s['numerator'] for s in stability.values()),36),
            stable_correct_by_category=stability, valid_triple_coverage=ratio(len(valid),12),
            repeat_disagreement=disagreement, outcomes=outcomes(mr),
            Reliability=ratio(sum(r['result']=='valid' for r in mr),36),
            FullCase=ratio(sum(all(correct(r,c) for c in CATEGORIES) for r in mr),36),
            per_repetition={str(rep):{c:ratio(sum(correct(r,c) for r in mr if r['repetition']==rep),12)
                                     for c in CATEGORIES} for rep in SEEDS})
    return dict(Score=ratio(sum(correct(r,c) for r in runs for c in CATEGORIES),324),
        StableCorrect=ratio(stable,108), Reliability=ratio(sum(r['result']=='valid' for r in runs),108),
        FullCase=ratio(sum(all(correct(r,c) for c in CATEGORIES) for r in runs),108),
        outcomes=outcomes(runs), models=models)


def difference(w, b):
    require(w['denominator']==b['denominator'], 'Unequal planned denominators')
    return ratio(w['numerator']-b['numerator'],w['denominator'])


def evaluate(inputs):
    require(inputs['format']=='sensitivity-d11-analysis-input-v1', 'Unexpected analysis schema')
    b, w = inputs['baseline_runs'], inputs['sensitivity_runs']
    validate(b,'P2'); validate(w,sf.PROMPT)
    require(all(x['reference']==y['reference'] for x,y in zip(b,w)), 'Baseline/reference mismatch')
    require(inputs['prompt_hashes']=={'P2':sf.PARENT_SHA,sf.PROMPT:sf.SHA}, 'Prompt binding mismatch')
    baseline, variant = describe(b), describe(w)
    models = {}; pooled_category = pooled_vector = paired_valid = 0
    for model in MODELS:
        pairs = [(x,y) for x,y in zip(b,w) if x['model']==model]
        both = [(x,y) for x,y in pairs if x['result']==y['result']=='valid']
        table = {a:{z:sum(x['result']==a and y['result']==z for x,y in pairs) for z in OUTCOMES} for a in OUTCOMES}
        cats = {c:ratio(sum(x['prediction'][c]!=y['prediction'][c] for x,y in both),len(both)) for c in CATEGORIES}
        vector = ratio(sum(any(x['prediction'][c]!=y['prediction'][c] for c in CATEGORIES) for x,y in both),len(both))
        bm, wm = baseline['models'][model],variant['models'][model]
        models[model] = dict(category_deltas={c:difference(wm['categories'][c],bm['categories'][c]) for c in CATEGORIES},
            ModelCorrect_delta=difference(wm['ModelCorrect'],bm['ModelCorrect']),
            paired_valid_coverage=ratio(len(both),36),excluded_failure_pairs=36-len(both),
            terminal_outcome_transitions=table,invalid_to_valid=sum(table[o]['valid'] for o in OUTCOMES if o!='valid'),
            valid_to_invalid=sum(table['valid'][o] for o in OUTCOMES if o!='valid'),
            category_disagreement=cats,vector_disagreement=vector)
        paired_valid += len(both); pooled_category += sum(v['numerator'] for v in cats.values())
        pooled_vector += vector['numerator']
    transitions = {a:{z:sum(m['terminal_outcome_transitions'][a][z] for m in models.values()) for z in OUTCOMES} for a in OUTCOMES}
    return dict(format=VERSION,diagnostic_only=True,protocol='prompt_development_protocol_v1.md §6 and §9/D11',
        fabricated=inputs.get('fabricated',False),baseline=baseline,variant=variant,
        Score_delta=difference(variant['Score'],baseline['Score']),models=models,
        pooled=dict(category_disagreement=ratio(pooled_category,3*paired_valid),
            vector_disagreement=ratio(pooled_vector,paired_valid),paired_valid_coverage=ratio(paired_valid,108),
            excluded_failure_pairs=108-paired_valid,terminal_outcome_transitions=transitions,
            invalid_to_valid=sum(m['invalid_to_valid'] for m in models.values()),
            valid_to_invalid=sum(m['valid_to_invalid'] for m in models.values())))
