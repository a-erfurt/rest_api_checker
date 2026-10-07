"""Interactive flow over fabricated metadata; no database or model calls."""
import pytest
from rest_api_checker import live_demo_cli, live_adhoc_runtime
from test_live_demo_cli import core, args, console


@pytest.fixture(autouse=True)
def metadata(monkeypatch):
    monkeypatch.setattr(live_adhoc_runtime, 'probe_runtime', lambda: dict(available=True, version='0.40.0', thesis_version='0.35.1', notice='⚠ Runtime differs from the qualified version: Ollama 0.40.0. Interactive checks remain available.'))
    monkeypatch.setattr(live_adhoc_runtime, 'model_availability', lambda: {'qwen3.6:27b': 'installed · not loaded'})


def run(core, answers, *flags):
    parsed=args(*flags); parsed.adhoc=True
    view, stream=console(); responses=iter(answers)
    value, code=live_demo_cli.run(object(), parsed, view, input_fn=lambda _: next(responses), interactive=True)
    return value,code,stream.getvalue()


def test_adhoc_default_one_p2_no_runtime_selection(core):
    core.paths[:]=[]
    value, code, text=run(core,['1','1','1','1','1','','n'])
    assert code==0 and value['status']=='CANCELLED'
    assert core.calls[0][1]['adhoc'] is True
    assert core.calls[0][1]['runtime_path'] is None
    assert core.calls[0][1]['repetitions']==1
    assert core.calls[0][1]['model_ids']==[4]
    for phrase in ('P2','Ollama 0.40.0','will not modify existing evaluation results','PPP','installed · not loaded'):
        assert phrase in ' '.join(text.split())
    for hidden in ('live demo','live/ad-hoc','10003','membership 11','Prompt ID','ID 4','Recovery evidence'):
        assert hidden not in text
    assert len(core.calls)==1


def test_adhoc_multiple_repetitions_and_confirmation_hides_run_ids(core):
    value, code, text=run(core,['1','1','1','1','2','3','yes'])
    assert code==0 and value['status']=='COMPLETED'
    assert core.calls[0][1]['repetitions']==3
    assert core.calls[0][1]['model_ids']==[8]
    assert [c[0] for c in core.calls]==['plan','execute']
    assert 'not installed' in text
    assert 'run 10004' not in text and 'attempt 1' not in text


def test_service_and_operation_filtering_no_database_ids(core):
    base=core.data['cases'][0]
    core.data['cases'] += [dict(base,id=12,service_id=9,service='Other',operation_id=30,path='/other',case_code='NATIVE-2'),
                          dict(base,id=13,operation_id=22,path='/second',case_code='NATIVE-3')]
    _,_,text=run(core,['1','2','1','1','1','','n'])
    assert core.calls[0][1]['case_id']==13
    assert 'NATIVE-3' in text and 'NATIVE-2' not in text and 'membership' not in text


def test_case_filter_uses_reference_vector(core):
    base=core.data['cases'][0]
    core.data['cases'] += [dict(base,id=12,case_code='FAULT',reference=['FAIL','NOT_APPLICABLE','NOT_APPLICABLE'])]
    _,_,text=run(core,['1','1','2','1','1','','n'])
    assert core.calls[0][1]['case_id']==12
    assert 'FNN' in text and 'DEV-01' not in text


def test_final_is_default_and_development_is_explicit(core):
    base=core.data['cases'][0]
    core.data['cases'].append(dict(base,id=82,dataset_id=3,dataset_name='Final evaluation',case_set_label='Final evaluation',case_code='V2-EDX-003'))
    core.data['default_dataset_id']=3
    _,_,text=run(core,['1','1','1','1','1','','n'])
    assert core.calls[0][1]['case_id']==82
    assert 'Case set: Final evaluation (default)' in text
    assert 'DEV-01' not in text
    core.calls.clear()
    _,_,text=run(core,['s','1','1','1','1','1','1','','n'])
    assert core.calls[0][1]['case_id']==11
    assert 'Other case sets' in text


def test_case_details_are_reachable_before_selection(core,monkeypatch):
    from rest_api_checker import interactive_evidence
    seen=[]
    monkeypatch.setattr(interactive_evidence,'show_case_details',lambda repo,row,view,read:seen.append(row['id']))
    _,_,text=run(core,['1','1','1','d 1','1','1','','n'])
    assert seen==[11] and 'Details / files' in text


def test_empty_filter_returns_to_filter_menu(core):
    _,_,text=run(core,['1','1','2','1','1','1','','n'])
    assert 'No cases of this type' in text
    assert core.calls[0][1]['case_id']==11


@pytest.mark.parametrize('answers',[['q'],['1','q','q'],['1','1','q','q','q'],['1','1','1','q','q','q','q'],['1','1','1','1','q']])
def test_back_selection_never_plans_or_executes(core,answers):
    value,code,_=run(core,answers)
    assert value['status']=='CANCELLED' and code==0 and not core.calls


def test_offline_ollama_does_not_block_selection_or_cancel(core,monkeypatch):
    monkeypatch.setattr(live_adhoc_runtime,'model_availability',lambda:None)
    value,code,text=run(core,['1','1','1','1','1','','n'])
    assert value['status']=='CANCELLED' and code==0
    assert 'Availability could not be checked' in text
