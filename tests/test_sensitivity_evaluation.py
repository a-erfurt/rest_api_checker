"""Hand-counted fabricated pairs; no persisted study predictions or scores."""
from copy import deepcopy
import pytest
from rest_api_checker import sensitivity_evaluation as e, sensitivity_freeze as sf
from rest_api_checker.experiment.schedule import comparison_schedule
from rest_api_checker.experiment.request import MODELS


def fixture():
    runs=[dict(id=s.run_order,case=s.case,model=s.model,prompt='P2',repetition=s.repetition,seed=s.seed,
        run_order=s.run_order,result='valid',reference=dict(c1='PASS',c2='FAIL',c3='NOT_APPLICABLE'),
        prediction=dict(c1='PASS',c2='FAIL',c3='NOT_APPLICABLE')) for s in comparison_schedule() if s.prompt=='P2']
    variant=deepcopy(runs)
    for i,r in enumerate(variant,1):r.update(id=1000+i,run_order=i,prompt=sf.PROMPT)
    return dict(format='sensitivity-d11-analysis-input-v1',fabricated=True,baseline_runs=runs,sensitivity_runs=variant,
                prompt_hashes={'P2':sf.PARENT_SHA,sf.PROMPT:sf.SHA})


def test_perfect_identity_no_selection():
    report=e.evaluate(fixture())
    assert report['diagnostic_only'] and 'selected_prompt' not in report and 'ranking' not in report
    for key,d in (('Score',324),('StableCorrect',108),('Reliability',108),('FullCase',108)):
        assert report['baseline'][key]==report['variant'][key]==e.ratio(d,d)
    assert report['Score_delta']==e.ratio(0,324)
    assert report['pooled']['category_disagreement']==e.ratio(0,324)
    assert report['pooled']['vector_disagreement']==e.ratio(0,108)


def test_independent_failure_transitions_and_wrong_applicability():
    f=fixture();model=MODELS[0]
    for phase in ('baseline_runs','sensitivity_runs'):
        for r in f[phase]:
            if r['model']==model and r['repetition']==1:
                if phase=='baseline_runs' and r['case']=='DEV-01':r.update(result='parser_failure',prediction=None)
                if phase=='sensitivity_runs' and r['case']=='DEV-02':r.update(result='technical_failure',prediction=None)
                if phase=='sensitivity_runs' and r['case']=='DEV-03':r['prediction']['c3']='PASS'
    report=e.evaluate(f);m=report['models'][model]
    assert report['baseline']['Score']==e.ratio(321,324)
    assert report['variant']['Score']==e.ratio(320,324)
    assert report['Score_delta']==e.ratio(-1,324)
    assert m['category_deltas']['c3']==e.ratio(-1,36)
    assert m['ModelCorrect_delta']==e.ratio(-1,108)
    assert m['paired_valid_coverage']==e.ratio(34,36)
    assert m['excluded_failure_pairs']==2 and m['invalid_to_valid']==m['valid_to_invalid']==1
    assert m['category_disagreement']['c3']==e.ratio(1,34)
    assert report['pooled']['category_disagreement']==e.ratio(1,318)
    assert report['pooled']['vector_disagreement']==e.ratio(1,106)
    wm=report['variant']['models'][model]
    assert wm['repeat_disagreement']['c3']==e.ratio(1,11)
    assert wm['stable_correct_by_category']['c3']==e.ratio(10,12)
    assert wm['per_repetition']['1']['c3']==e.ratio(10,12)
    assert wm['FullCase']==e.ratio(34,36)


def test_no_valid_pairs_is_na_failures_stay_in_denominator():
    f=fixture()
    for r in f['sensitivity_runs']:r.update(result='parser_failure',prediction=None)
    report=e.evaluate(f)
    assert report['variant']['Reliability']==e.ratio(0,108)
    assert report['variant']['Score']==e.ratio(0,324)
    assert report['pooled']['vector_disagreement']==e.ratio(0,0)
    assert report['pooled']['valid_to_invalid']==108
    assert report['variant']['models'][MODELS[0]]['repeat_disagreement']['vector']==e.ratio(0,0)


@pytest.mark.parametrize('change',[
    lambda f:f['sensitivity_runs'].pop(),
    lambda f:f['sensitivity_runs'].__setitem__(1,deepcopy(f['sensitivity_runs'][0])),
    lambda f:f['sensitivity_runs'][0].update(seed=999),
    lambda f:f['sensitivity_runs'][0].update(repetition=2),
    lambda f:f['sensitivity_runs'][0].update(prompt='P1'),
    lambda f:f['sensitivity_runs'][0].update(result=None),
    lambda f:f['sensitivity_runs'][0].update(prediction=None),
    lambda f:f['sensitivity_runs'][0]['reference'].update(c1='FAIL'),
    lambda f:f['prompt_hashes'].update(P2='0'*64),
    lambda f:f.update(format='unapproved'),
])
def test_fail_closed(change):
    f=fixture();change(f)
    with pytest.raises(ValueError):e.evaluate(f)
