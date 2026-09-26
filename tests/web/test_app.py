"""HTTP presentation, evidence safety and read-only boundaries; no SQL required."""
from contextlib import contextmanager
from html import unescape
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import ast
import re

import pyodbc
import pytest
from fastapi.testclient import TestClient

from .browser_fixture import HASH, HOSTILE, query_factory
from rest_api_checker.web.app import create_app


@pytest.mark.parametrize('url', ['/', '/overview', '/evaluation', '/runs', '/runs/1', '/data',
                                '/data/datasets','/data/cases','/data/references','/data/artifacts'])
def test_routes_available(client, url):
    response = client.get(url)
    assert response.status_code == 200
    assert 'RestApiChecker' in response.text


def test_startup_lazy_without_database(monkeypatch):
    monkeypatch.delenv('RAC_WEB_ENV_FILE', raising=False)
    monkeypatch.delenv('RAC_WEB_DATABASE', raising=False)
    app = create_app()
    with TestClient(app) as client:
        response = client.get('/')
    assert response.status_code in (200,503)
    assert 'unavailable' in response.text.lower() or 'not configured' in response.text.lower()


def test_default_connection_is_lazy_rollback_only_and_closed(monkeypatch):
    from rest_api_checker.web import app as module
    events=[]
    class Connection:
        timeout=60
        def rollback(self): events.append('rollback')
        def close(self): events.append('close')
        def commit(self): pytest.fail('Read-only connection must not commit')
    connection=Connection()
    monkeypatch.setenv('RAC_WEB_ENV_FILE','/fabricated-private-settings')
    monkeypatch.setattr(module,'read_settings',lambda path:{'fabricated':True})
    def connect(*args,**kwargs):
        events.append('connect')
        return connection
    monkeypatch.setattr(module,'connect',connect)
    create_app()
    assert events==[]
    with module.database_queries() as query:
        assert not hasattr(query,'plan_experiment')
    assert events==['connect','rollback','close']


def test_launcher_defaults_to_loopback(monkeypatch):
    import os
    import sys
    import uvicorn
    from rest_api_checker.web.app import main
    calls=[]
    monkeypatch.setenv('RAC_WEB_DATABASE','fabricated-test-database')
    monkeypatch.setattr(sys,'argv',['rest-api-checker-web'])
    monkeypatch.setattr(uvicorn,'run',lambda app,**kwargs:calls.append(kwargs))
    main()
    assert calls==[dict(host='127.0.0.1',port=8000)]
    assert os.environ['RAC_WEB_DATABASE']=='fabricated-test-database'


def test_overview_no_experiments(client, queries):
    queries.mode='empty'
    response=client.get('/')
    assert response.status_code==200
    assert re.search(r'no experiment|no data',response.text,re.I)
    assert 'every 3s' not in response.text


def test_running_overview_operational_counts_and_polling(client, queries):
    response=client.get('/')
    assert response.status_code==200
    for label in ('Progress','Valid','Parser','Technical','217','324','FAB-001'):
        assert label in response.text
    assert 'every 3s' in response.text
    assert '67.0%' in response.text
    assert ('overview',{'experiment_id':1}) in queries.calls
    assert not any(name=='report' for name,_ in queries.calls)


def test_completed_overview_stops_polling(client, queries):
    queries.mode='completed'
    response=client.get('/')
    for label in ('Selected Prompt','Score','Robust','Reliability','FullCase'):
        assert label in response.text
    assert 'every 3s' not in response.text
    assert ('report',{'experiment_id':2}) in queries.calls


def test_incomplete_evaluation_never_requests_report(client, queries):
    response=client.get('/evaluation?experiment=1')
    assert response.status_code==200
    assert '217' in response.text and '324' in response.text
    assert re.search(r'evaluation.*(available|completion|complete)',response.text,re.I|re.S)
    assert not any(name=='report' for name,_ in queries.calls)
    assert '<canvas' not in response.text


@pytest.mark.parametrize('url',['/evaluation?experiment=2','/?experiment=2','/fragments/overview?experiment=2'])
def test_finished_timestamp_with_pending_runs_cannot_publish_metrics(client,queries,monkeypatch,url):
    original=queries.experiments
    def unreconciled():
        records=original()
        for row in records:
            if row['id']==2:
                row.update(pending=1,completed=323,valid=321,state='incomplete')
        return records
    monkeypatch.setattr(queries,'experiments',unreconciled)
    response=client.get(url)
    assert response.status_code==200 and '323' in response.text
    assert not any(name=='report' for name,_ in queries.calls)
    assert '<canvas' not in response.text


def test_completed_evaluation_uses_persisted_metrics(client, queries):
    response=client.get('/evaluation?experiment=2')
    assert response.status_code==200
    for label in ('Score','Robust','StableCorrect','Reliability','FullCase','C1','C2','C3',
                  'Qwen','Gemma','Mistral','Detailed diagnostics'):
        assert label in response.text
    assert '<canvas' in response.text
    assert '108' in response.text and '324' in response.text
    assert ('report',{'experiment_id':2}) in queries.calls


def test_prompt_default_uses_only_explicit_selected_prompt(client,queries):
    selected=queries.saved_report['selected_prompt']
    response=client.get('/evaluation?experiment=2')
    assert re.search(r'<a[^>]*aria-current="page"[^>]*>'+selected+'</a>',response.text)
    queries.saved_report.pop('selected_prompt')
    response=client.get('/evaluation?experiment=2')
    assert re.search(r'<a[^>]*aria-current="page"[^>]*>P1</a>',response.text)
    assert 'no selection recorded' in response.text
    assert 'P2' in response.text and 'P3' in response.text


def test_global_selection_prefers_started_then_latest_completed():
    from rest_api_checker.web.app import select_experiment
    earlier=dict(id=99,started_at='2026-09-20',finished_at='2026-09-20')
    latest=dict(id=1,started_at='2026-09-25',finished_at='2026-09-25')
    unfinished=dict(id=2,started_at='2026-09-19',finished_at=None)
    planned=dict(id=200,started_at=None,finished_at=None)
    assert select_experiment([earlier,latest,unfinished,planned],None)==unfinished
    assert select_experiment([earlier,latest,planned],None)==latest
    assert select_experiment([earlier,latest,unfinished],99)==earlier


@pytest.mark.parametrize('running',[False,True])
def test_global_selection_compares_timezone_offsets_chronologically(running):
    from rest_api_checker.web.app import select_experiment
    earlier=dict(id=99,started_at='2026-09-26T14:00:00.1234567+05:45',
                 finished_at=None if running else '2026-09-26T14:00:00.1234567+05:45')
    latest=dict(id=1,started_at='2026-09-26T09:00:00.1234567+00:00',
                finished_at=None if running else '2026-09-26T09:00:00.1234567+00:00')
    assert select_experiment([earlier,latest],None)==latest


def test_absent_report_explicit_unavailable(client,queries):
    queries.mode='no_report'
    response=client.get('/evaluation')
    assert response.status_code==200
    assert re.search(r'(no persisted|not available|unavailable|no evaluation)',response.text,re.I)
    assert '<canvas' not in response.text


def test_completed_without_selection_does_not_guess_winner(client,queries):
    queries.mode='no_report'
    response=client.get('/')
    assert response.status_code==200
    assert 'Selected Prompt' in response.text
    assert re.search(r'not available|unavailable|not yet|no persisted',response.text,re.I)
    assert 'every 3s' not in response.text


@pytest.mark.parametrize('missing',[True,False])
def test_overview_missing_or_null_selection_has_explicit_unavailable_metrics(client,queries,missing):
    if missing:
        queries.saved_report.pop('selected_prompt')
    else:
        queries.saved_report['selected_prompt']=None
    response=client.get('/?experiment=2')
    assert response.status_code==200
    for metric in ('Selected Prompt','Score','Robust','Reliability','FullCase'):
        assert f'<dt>{metric}</dt><dd>Not available</dd>' in response.text


@pytest.mark.parametrize('url',['/evaluation?experiment=2','/?experiment=2','/fragments/overview?experiment=2'])
def test_unreadable_report_preserves_operational_context(client,queries,monkeypatch,url):
    from rest_api_checker.web.queries import ReportUnavailable
    def unreadable(identifier):
        raise ReportUnavailable('Persisted evaluation report is unreadable')
    monkeypatch.setattr(queries,'report',unreadable)
    response=client.get(url)
    assert response.status_code==200
    assert re.search(r'(evaluation|report).*unavailable',response.text,re.I|re.S)
    assert 'Database unavailable' not in response.text
    assert '324' in response.text and '<canvas' not in response.text


@pytest.mark.parametrize('format_name',['future-evaluation-v2','not-a-report'])
def test_unsupported_report_has_evaluation_unavailable_state(client,queries,format_name):
    queries.saved_report['format']=format_name
    response=client.get('/evaluation?experiment=2')
    assert response.status_code==200
    assert re.search(r'(evaluation|report).*unavailable|Evaluation not available',response.text,re.I|re.S)
    assert '<canvas' not in response.text and 'Database unavailable' not in response.text


def test_malformed_report_projection_is_explicitly_unavailable(client,queries):
    selected=queries.saved_report['selected_prompt']
    first_model=next(iter(queries.saved_report['metrics'][selected]['cells']))
    queries.saved_report['metrics'][selected]['cells'][first_model]['c1']='invalid persisted ratio'
    response=client.get('/evaluation?experiment=2')
    assert response.status_code==200
    assert re.search(r'(evaluation|report).*unavailable|Evaluation not available',response.text,re.I|re.S)
    assert '<canvas' not in response.text and 'Database unavailable' not in response.text


def test_runs_server_pagination_forwarded_and_bounded(client,queries):
    response=client.get('/runs?page=2')
    assert response.status_code==200
    parameters=next(p for name,p in queries.calls if name=='runs')
    assert parameters['page']==2 and parameters['page_size']==50
    assert 'FAB-051' in response.text and 'FAB-100' in response.text
    assert 'FAB-050' not in response.text and 'FAB-101' not in response.text


def test_runs_filters_are_forwarded_to_query(client,queries):
    response=client.get('/runs?experiment=1&model=2&prompt=2&status=parser_failure&repetition=2')
    assert response.status_code==200
    parameters=next(p for name,p in queries.calls if name=='runs')
    assert {k:parameters[k] for k in ('experiment_id','model_id','prompt_id','status','repetition')} == dict(
        experiment_id=1,model_id=2,prompt_id=2,status='parser_failure',repetition=2)
    assert 'FAB-002' in response.text and 'FAB-001' not in response.text


def test_blank_optional_form_filters_are_accepted(client,queries):
    response=client.get('/runs?experiment=1&model=&prompt=&status=&search=&repetition=&page_size=50')
    assert response.status_code==200
    parameters=next(p for name,p in queries.calls if name=='runs')
    assert parameters==dict(experiment_id=1,model_id=None,prompt_id=None,status=None,
                            search='',repetition=None,page=1,page_size=50)
    assert 'FAB-001' in response.text


def test_case_search_forwarded_to_query(client,queries):
    response=client.get('/runs?search=FAB-123')
    assert response.status_code==200
    assert next(p for n,p in queries.calls if n=='runs')['search']=='FAB-123'
    assert 'FAB-123' in response.text and 'FAB-122' not in response.text


@pytest.mark.parametrize('identifier,status',[(1,'PASS'),(2,'PARSER FAILURE'),(3,'TECHNICAL FAILURE')])
def test_run_outcomes_and_verdicts(client,identifier,status):
    response=client.get(f'/runs/{identifier}')
    assert response.status_code==200
    assert status in response.text
    assert 'FAIL' in response.text and 'NOT_APPLICABLE' in response.text


def test_unfinished_run_does_not_fabricate_prediction(client):
    response=client.get('/runs/4')
    assert response.status_code==200
    assert re.search(r'pending|unfinished|not available|no prediction',response.text,re.I)
    assert 'Fabricated model reason' not in response.text


def test_raw_output_without_persisted_evidence_is_explicitly_unavailable(client,queries,monkeypatch):
    original=queries.run_detail
    def pending(*args,**kwargs):
        detail=original(*args,**kwargs)
        detail.update(attempts=[],evidence=[])
        return detail
    monkeypatch.setattr(queries,'run_detail',pending)
    response=client.get('/runs/4?tab=raw')
    assert response.status_code==200
    assert 'No persisted provider output is available.' in response.text


@pytest.mark.parametrize('tab',['reasons','response','openapi','raw','attempts'])
def test_run_evidence_tabs_safely_escape_content(client,queries,tab):
    response=client.get(f'/runs/1?tab={tab}')
    assert response.status_code==200
    assert ('run_detail',{'id':1,'tab':tab}) in queries.calls
    assert HOSTILE not in response.text
    assert '<img src=x' not in response.text
    assert '&lt;script&gt;' in response.text


def test_response_tab_retains_http_metadata_and_long_viewer(client):
    response=client.get('/runs/1?tab=response')
    assert '422' in response.text and 'application/json' in response.text
    assert 'Show full' in response.text and '<details' in response.text
    assert 'Fabricated evidence line 199' in response.text


@pytest.mark.parametrize('section',['datasets','cases','references','artifacts'])
def test_data_tables_and_detail(client,queries,section):
    response=client.get('/data/'+section)
    assert response.status_code==200
    assert ('data_list',dict(section=section,page=1,page_size=50,kind='models')) in queries.calls
    detail=client.get(f'/data/{section}/1')
    assert detail.status_code==200
    assert 'Technical Details' in detail.text
    assert HASH in detail.text and HOSTILE not in detail.text
    assert '&lt;script&gt;' in detail.text


@pytest.mark.parametrize('kind,display',[
    ('models',('27.000 B','Q4_K_M')),
    ('prompts',('direct','v1')),
    ('configs',('Context 32768','output 4096','Temperature 0.100')),
    ('contracts',('OpenAPI 3.1.0',)),
    ('files',('1234 bytes',)),
    ('experiments',('comparison',)),
    ('reports',('2026-09-26T11:00:00+00:00',)),
])
def test_artifact_lists_use_real_projection_fields(client,kind,display):
    response=client.get('/data/artifacts?kind='+kind)
    assert response.status_code==200
    assert all(value in response.text for value in display)


def test_data_navigation_preserves_global_experiment(client):
    redirected=client.get('/data?experiment=2')
    assert redirected.status_code==200
    assert redirected.url.path=='/data/datasets' and redirected.url.params['experiment']=='2'
    response=client.get('/data/artifacts?kind=prompts&experiment=2')
    links=[urlsplit(unescape(href)) for href in re.findall(r'href="([^"]+)"',response.text)]
    for path in ('/data/datasets','/data/cases','/data/references','/evaluation','/runs'):
        assert any(link.path==path and parse_qs(link.query).get('experiment')==['2'] for link in links)
    assert any(link.path=='/data/artifacts/1' and parse_qs(link.query)==dict(kind=['prompts'],experiment=['2'])
               for link in links)
    detail=client.get('/data/artifacts/1?kind=prompts&experiment=2')
    links=[urlsplit(unescape(href)) for href in re.findall(r'href="([^"]+)"',detail.text)]
    assert any(link.path=='/data/artifacts' and parse_qs(link.query)==dict(kind=['prompts'],experiment=['2'])
               for link in links)


def test_data_relations_preserve_explicit_experiment_target(client,queries,monkeypatch):
    original=queries.data_detail
    def linked(*args,**kwargs):
        detail=original(*args,**kwargs)
        detail['relationships']=[dict(title='Own experiment',url='/evaluation?experiment=99'),
                                 dict(title='Contract',url='/data/artifacts/2?kind=contracts')]
        return detail
    monkeypatch.setattr(queries,'data_detail',linked)
    response=client.get('/data/artifacts/1?kind=reports&experiment=2')
    links=[urlsplit(unescape(href)) for href in re.findall(r'href="([^"]+)"',response.text)]
    assert any(link.path=='/evaluation' and parse_qs(link.query)==dict(experiment=['99']) for link in links)
    assert any(link.path=='/data/artifacts/2' and parse_qs(link.query)==dict(kind=['contracts'],experiment=['2'])
               for link in links)


def test_not_found_detail(client):
    assert client.get('/runs/99999').status_code==404
    assert client.get('/data/cases/99999').status_code==404


def test_polling_is_fragment_only_and_stops_after_completion(client,queries):
    running=client.get('/fragments/overview?experiment=1',headers={'HX-Request':'true'})
    assert running.status_code==200 and '<html' not in running.text.lower()
    assert 'every 3s' in running.text
    complete=client.get('/fragments/overview?experiment=2',headers={'HX-Request':'true'})
    assert complete.status_code==200 and 'every 3s' not in complete.text


def test_database_unavailable_does_not_expose_credentials():
    @contextmanager
    def unavailable():
        raise pyodbc.OperationalError('UID=sa;PWD=super-secret;driver internal')
        yield
    with TestClient(create_app(query_factory=unavailable)) as client:
        for url in ('/','/runs','/evaluation','/data/cases','/fragments/overview?experiment=1'):
            response=client.get(url)
            assert response.status_code in (200,503)
            assert re.search(r'unavailable|paused',response.text,re.I)
            assert 'super-secret' not in response.text and 'UID=sa' not in response.text


def test_routes_structurally_read_only(client):
    for route in client.app.routes:
        if hasattr(route,'methods'):
            assert route.methods <= {'GET','HEAD'}
    for method in ('post','put','patch','delete'):
        response=getattr(client,method)('/runs/1')
        assert response.status_code==405


def test_no_web_imports_of_mutable_execution_services():
    root=Path(__file__).resolve().parents[2]/'src/rest_api_checker/web'
    forbidden=('orchestration','batch','provider','preflight','demo','importer','admin')
    for source in root.rglob('*.py'):
        tree=ast.parse(source.read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.ImportFrom):
                assert not set((node.module or '').split('.')) & set(forbidden), source
                assert not {'Repository','evaluate','create_report','analysis_input'} & {a.name for a in node.names}, source


def test_static_ui_controls_and_safety_policy(client):
    response=client.get('/')
    assert 'Focus' in response.text and 'collapse' in response.text.lower()
    assert 'Content-Security-Policy' in response.headers
    assert 'object-src' in response.headers['Content-Security-Policy']
    assert 'onclick=' not in response.text


def test_templates_and_first_party_scripts_do_not_insert_untrusted_html():
    root=Path(__file__).resolve().parents[2]/'src/rest_api_checker/web'
    for template in (root/'templates').rglob('*.html'):
        assert not re.search(r'\|\s*safe\b',template.read_text()), template
    for script in (root/'static').glob('*.js'):
        source=script.read_text()
        assert '.innerHTML' not in source and 'insertAdjacentHTML' not in source, script


@pytest.mark.parametrize('url',['/runs?page=0','/runs?page_size=100000','/runs?model=-1','/runs/0'])
def test_invalid_query_values_rejected(client,url):
    assert client.get(url).status_code in (400,404,422)
