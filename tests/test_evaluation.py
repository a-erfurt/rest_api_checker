"""Independent hand-counted outcomes; no model/provider needed."""
from copy import deepcopy

import pytest

from rest_api_checker import evaluation as e
from rest_api_checker.experiment.schedule import comparison_schedule
from rest_api_checker.experiment.request import MODELS


def fixture():
    return dict(fabricated=True,prompt_lengths={'P1':4325,'P2':4996,'P3':5835},runs=[dict(id=s.run_order,
        case=s.case,prompt=s.prompt,model=s.model,repetition=s.repetition,seed=s.seed,run_order=s.run_order,
        result='valid',reference=dict(c1='PASS',c2='FAIL',c3='NOT_APPLICABLE'),
        prediction=dict(c1='PASS',c2='FAIL',c3='NOT_APPLICABLE')) for s in comparison_schedule()])


def test_perfect_all_metrics_na_and_length_tie():
    r = e.evaluate(fixture())
    for p in ('P1','P2','P3'):
        for key,d in [('Score',324),('Robust',36),('StableCorrect',108),('Reliability',108),('FullCase',108)]:
            assert r['metrics'][p][key]==e.ratio(d,d)
        for model in MODELS:
            diag = r['diagnostics'][p][model]
            assert diag['confusion']['c3']['NOT_APPLICABLE']['NOT_APPLICABLE']==36
            assert diag['valid_triple_coverage']==e.ratio(12,12)
            assert diag['repeat_disagreement']['vector']==e.ratio(0,12)
    assert r['ranking']==['P1','P2','P3'] and r['selection_decided_by']=='Length'
    assert [s['criterion'] for s in r['tie_break_trace']]==list(e.CRITERIA[:-1])


def test_hand_computed_failures_stability_and_disagreement():
    f = fixture()
    # P1 / first model: case 1 rep 1 parser failure, case 2 rep 1
    # terminal technical failure, case 3 rep 1 wrong C3 applicability.
    for r in f['runs']:
        if r['prompt']=='P1' and r['model']==MODELS[0] and r['repetition']==1:
            if r['case'] in ('DEV-01','DEV-02'):
                r.update(result='parser_failure' if r['case']=='DEV-01' else 'technical_failure',prediction=None)
            elif r['case']=='DEV-03':
                r['prediction']['c3']='PASS'
    result = e.evaluate(f)
    m = result['metrics']['P1']
    assert m['Score']==e.ratio(317,324)  # 6 failure losses + one wrong verdict
    assert m['Robust']==e.ratio(33,36)
    assert m['StableCorrect']==e.ratio(101,108)  # two lost triples x 3 categories + one
    assert m['Reliability']==e.ratio(106,108)
    assert m['FullCase']==e.ratio(105,108)
    d = result['diagnostics']['P1'][MODELS[0]]
    assert d['valid_only']['c3']==e.ratio(33,34)
    assert d['valid_coverage']==e.ratio(34,36)
    assert d['valid_triple_coverage']==e.ratio(10,12)
    assert d['repeat_disagreement']['vector']==e.ratio(1,10)
    assert d['repeat_disagreement']['c1']==e.ratio(0,10)
    assert d['per_repetition']['1']['c3']==e.ratio(9,12)
    assert d['confusion']['c3']['NOT_APPLICABLE']['PASS']==1
    assert sum(sum(v.values()) for v in d['confusion']['c3'].values())==34
    assert result['ranking']==['P2','P3','P1']


def test_all_failures_undefined_is_null_not_na_verdict():
    f = fixture()
    for r in f['runs']:
        r.update(result='technical_failure',prediction=None)
    result = e.evaluate(f)
    assert result['metrics']['P1']['Score']==e.ratio(0,324)
    d = result['diagnostics']['P1'][MODELS[0]]
    assert d['valid_only']['c1']==dict(numerator=0,denominator=0,value=None)
    assert d['repeat_disagreement']['vector']==e.ratio(0,0)
    assert d['valid_triple_coverage']==e.ratio(0,12)


@pytest.mark.parametrize('criterion',e.CRITERIA)
def test_each_exact_tie_breaker(criterion):
    metrics = {p:{c:e.ratio(1,2) for c in e.CRITERIA[:5]} | dict(Length=10,Order=i)
               for i,p in enumerate(('P1','P2','P3'))}
    if criterion in e.CRITERIA[:5]:
        # Difference far below any display rounding precision must still decide.
        metrics['P3'][criterion]=e.ratio(500000000001,1000000000000)
    elif criterion=='Length':
        metrics['P3']['Length']=9
    ranking,trace = e.rank(metrics)
    assert ranking[0]==('P1' if criterion=='Order' else 'P3')
    assert trace[-1]['criterion']==criterion


@pytest.mark.parametrize('change',['missing','extra','duplicate','pending','prediction','reference','seed'])
def test_reject_unaccountable_inputs(change):
    f = fixture()
    if change=='missing': f['runs'].pop()
    if change=='extra': f['runs'].append(deepcopy(f['runs'][0]))
    if change=='duplicate': f['runs'][1]['id']=f['runs'][0]['id']
    if change=='pending': f['runs'][0]['result']=None
    if change=='prediction': f['runs'][0]['prediction']=None
    if change=='reference': f['runs'][0]['reference']['c1']='FAIL'
    if change=='seed': f['runs'][0]['seed']=999
    with pytest.raises(ValueError): e.evaluate(f)
