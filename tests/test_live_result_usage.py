"""Result usage presentation from stored/fabricated telemetry; no model calls."""
from copy import deepcopy
from io import StringIO

import pytest
from rich.console import Console

from rest_api_checker import live_result
from test_live_result import detail


def console(width=80):
    return Console(file=StringIO(), width=width, color_system=None,
                   force_terminal=False, markup=False, highlight=False)


def with_usage():
    stored = detail(model='gemma3:27b')
    stored['usage'] = dict(input_tokens=1200, output_tokens=85, total_tokens=1285,
        context_limit=32768, input_context_percent=1200/32768*100,
        attempt=1, attempt_count=1)
    return stored


@pytest.mark.parametrize('width', [80, 96])
def test_result_shows_counts_and_requested_context_within_panel_width(width):
    stored = with_usage()
    before = deepcopy(stored)
    view = console(width)
    live_result.show(view, stored)
    text = view.file.getvalue()
    for expected in ('Tokens: Input 1,200 · Output 85 · Total 1,285',
                     'Context limit: 32,768 tokens (requested) · Input 3.7%',
                     '✓ Run completed', '1.2 s', 'Overall: ✓ CORRECT', 'Parser: ✓ VALID'):
        assert expected in text
    assert text.index('Tokens:') < text.index('C1 Status')
    assert max(map(len, text.splitlines())) <= width
    assert len(text.splitlines()) <= 17
    assert '…' not in text and 'peak' not in text and 'budget_units' not in text
    assert stored == before


@pytest.mark.parametrize('status', ['valid', 'parser_failure', 'technical_failure'])
def test_reported_counts_remain_visible_when_prediction_is_unusable(status):
    stored = detail(status=status)
    stored['attempts'][0].update(prompt_tokens=824, output_tokens=42)
    view = console()
    live_result.show(view, stored)
    text = view.file.getvalue()
    assert 'Tokens: Input 824 · Output 42 · Total 866' in text
    assert 'Context limit: not recorded' in text
    if status != 'valid':
        assert 'NO PREDICTION' in text and 'Parser: ✗ NO USABLE OUTPUT' in text
        assert 'Overall: ✓ CORRECT' not in text


def test_partial_counts_do_not_invent_total_or_context_percentage():
    stored = detail()
    stored['attempts'][0].update(prompt_tokens=1200, output_tokens=None)
    view = console()
    live_result.show(view, stored)
    text = view.file.getvalue()
    assert 'Tokens: Input 1,200 · Output not recorded · Total not recorded' in text
    assert 'Context limit: not recorded' in text
    assert '%' not in text and 'Total 0' not in text


def test_zero_counts_are_distinct_from_missing_counts():
    stored = detail()
    stored['usage'] = dict(input_tokens=0, output_tokens=0, total_tokens=0,
        context_limit=32768, input_context_percent=0.0, attempt_count=1)
    view = console()
    live_result.show(view, stored)
    text = view.file.getvalue()
    assert 'Tokens: Input 0 · Output 0 · Total 0' in text
    assert 'Input 0.0%' in text and 'not recorded' not in text


def test_latest_attempt_counts_are_not_summed_while_duration_is_total():
    stored = detail()
    stored['attempts'] = [dict(attempt=1, prompt_tokens=1000, output_tokens=5, duration_ms=1000),
                          dict(attempt=2, prompt_tokens=1000, output_tokens=80, duration_ms=2000)]
    view = console()
    live_result.show(view, stored)
    text = view.file.getvalue()
    assert '3.0 s' in text
    assert 'Tokens: Input 1,000 · Output 80 · Total 1,080' in text
    assert 'Token counts: latest attempt. Duration includes all attempts.' in text
    assert 'Input 2,000' not in text and 'Total 2,085' not in text


def test_details_show_every_attempt_counts_and_missing_values():
    stored = detail()
    stored['attempts'] = [dict(attempt=1, prompt_tokens=1000, output_tokens=5),
                          dict(attempt=2, prompt_tokens=1000, output_tokens=None)]
    view = console()
    live_result.show_details(view, stored)
    text = view.file.getvalue()
    assert text.count('Attempt details') == 2
    assert text.count('Input tokens') == 2 and text.count('Output tokens') == 2
    assert '1,005' in text and 'not recorded' in text


@pytest.mark.parametrize('width', [80, 96])
def test_repetitions_keep_comparison_and_add_usage_table(width):
    records = [detail(model='gemma3:27b', repetition=1),
               detail(model='gemma3:27b', repetition=2, status='parser_failure', prediction=None)]
    records[0]['usage'] = with_usage()['usage']
    records[1]['attempts'][0].update(prompt_tokens=1200, output_tokens=None)
    before = deepcopy(records)
    view = console(width)
    live_result.repetitions(view, records)
    text = view.file.getvalue()
    for expected in ('Repetitions · Gemma 3 27B', 'Usable output 1/2', 'Reference', 'Prediction',
                     'Input', 'Output', 'Total', 'Context limit', '1,200', '1,285', '32,768', 'not recorded',
                     'Tokens per latest attempt · Context limit requested'):
        assert expected in text
    assert max(map(len, text.splitlines())) <= width
    assert '…' not in text and 'Run completed' not in text
    assert '80001' not in text and 'recovery-hidden-path' not in text
    assert records == before


def test_large_counts_are_not_shortened_or_clamped():
    stored = with_usage()
    stored['usage'].update(input_tokens=2147483647, output_tokens=2147483647,
                           total_tokens=4294967294, input_context_percent=125.0)
    records = [stored, deepcopy(stored)]
    view = console()
    live_result.show(view, stored)
    live_result.repetitions(view, records)
    text = view.file.getvalue()
    assert '2,147,483,647' in text and '4,294,967,294' in text
    assert 'Input 125.0%' in text
    assert '…' not in text and max(map(len, text.splitlines())) <= 80
