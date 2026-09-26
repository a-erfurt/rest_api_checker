import io
import json
from pathlib import Path

import pytest

from rest_api_checker import cli, preflight, terminal
from rest_api_checker.evaluation import ratio

ROOT = Path(__file__).resolve().parents[1]


def test_json_preflight_truthful(capsys):
    code = cli.main(['preflight','--root',str(ROOT),'--json'])
    captured = capsys.readouterr()
    value = json.loads(captured.out)
    assert code==3 and value['status']=='BLOCKED'
    assert sum(c['status']=='PASS' for c in value['checks'])==9
    assert {c['check'] for c in value['checks'] if c['status']=='BLOCKED'}=={
        'Database schema','Gate-B artifact acceptance'}
    assert not value['inference_performed'] and '\x1b' not in captured.out


def test_plain_preflight(capsys):
    assert cli.main(['preflight','--plain','--root',str(ROOT)])==3
    out = capsys.readouterr().out
    assert '[PASS]' in out and '[BLOCKED]' in out and '\x1b' not in out


def test_json_error_stdout_and_stderr(capsys):
    assert cli.main(['experiment','show','1','--json'])==3
    captured = capsys.readouterr()
    assert json.loads(captured.out)['status']=='BLOCKED'
    assert '--env-file' in captured.err


def test_preflight_missing_sources_fail(tmp_path):
    result = preflight.check(tmp_path,tmp_path)
    assert result['status']=='FAIL'
    assert result['checks'][0]['status']=='FAIL'


@pytest.mark.parametrize('no_color',[False,True])
def test_noninteractive_no_ansi_and_logical_progress(monkeypatch,no_color):
    if no_color: monkeypatch.setenv('NO_COLOR','1')
    stream = io.StringIO()
    console = terminal.console(file=stream)
    state = dict(planned=324,completed=0,pending=324,counts=dict(valid=0,parser_failure=0,technical_failure=0))
    with terminal.RunDisplay(console) as d:
        assert not d.live_enabled
        d.event(dict(event='start',state=state))
        d.event(dict(event='retry',message='Technical failure — retrying identical request (attempt 2/2)'))
        assert d.progress.tasks[0].completed==0 and d.progress.tasks[0].total==324
        for _ in range(50): d.event(dict(event='progress',state=state))
        d.event(dict(event='progress',state={**state,'completed':1,'pending':323,'counts':dict(valid=1,parser_failure=0,technical_failure=0)}))
        assert d.progress.tasks[0].completed==1
    out = stream.getvalue()
    assert '\x1b' not in out and out.count('0/324')==1 and '325' not in out


def test_na_metric_and_untrusted_terminal_text():
    assert terminal.metric(ratio(0,0))=='N/A (0/0)'
    assert terminal.clean('\x1b[31m[red]provider')=='\\x1b[31m[red]provider'


def test_options_before_and_after_command():
    for args in (['--json','experiment','show','1'],['experiment','show','1','--json']):
        assert cli.arguments().parse_args(args).json


def test_no_color_overrides_terminal_environment(monkeypatch):
    monkeypatch.setenv('NO_COLOR','1')
    monkeypatch.setenv('FORCE_COLOR','1')
    console = terminal.console(file=io.StringIO())
    assert console.color_system is None and not console.is_terminal


def test_live_panel_contains_hierarchy():
    from rich.console import Console
    stream = io.StringIO()
    console = Console(file=stream,force_terminal=True,width=100)
    d = terminal.RunDisplay(console)
    d.current = dict(model='qwen3.6:27b',prompt='P2',case='DEV-08',repetition=2,attempt=2)
    d.state = dict(planned=324,completed=217,pending=107,counts=dict(valid=210,parser_failure=5,technical_failure=2))
    d.progress.update(d.task,completed=217)
    console.print(d)
    out = stream.getvalue()
    for text in ('Progress','217 / 324','67%','Elapsed','Current','qwen3.6:27b','P2','DEV-08','2 / 3','2 / 2',
                 'Results','Parser failures','Technical failures','Pending','107'):
        assert text in out
