"""Compact result views keep provenance optional and parser failures final."""
from copy import deepcopy
import io

import pytest
from rich.console import Console

from rest_api_checker import live_result


@pytest.fixture(params=[80, 100])
def console(request):
    return Console(file=io.StringIO(), width=request.param, color_system=None,
                   force_terminal=False, markup=False, highlight=False)


def detail(reference=('PASS', 'PASS', 'PASS'), prediction=('PASS', 'PASS', 'PASS'),
           *, status='valid', model='Fabricated model', repetition=1):
    return dict(run=dict(id=80000+repetition, experiment_id=90001, repetition=repetition,
                         result=status, seed=101),
                case='CASE-SYNTHETIC', model=model, reference=dict(zip(live_result.CATEGORIES, reference)),
                prediction={**dict(zip(live_result.CATEGORIES, prediction)),
                            **{c+'_reason': 'Stored '+c+' explanation.' for c in live_result.CATEGORIES}}
                           if prediction else None,
                attempts=[dict(id=71001, attempt=1, response_file_id=72001, duration_ms=1234,
                               error_kind=None)], spool='/private/recovery-hidden-path')


def test_valid_result_is_compact_and_hides_technical_details(console):
    stored = detail()
    before = deepcopy(stored)
    live_result.show(console, stored)
    text = console.file.getvalue()
    for phrase in ('✓ Run completed', '1.2 s', 'CASE-SYNTHETIC', 'Fabricated model',
                   'Reference: PPP', 'Prediction: PPP', 'Overall: ✓ CORRECT', 'Parser: ✓ VALID',
                   'C1 Status', 'C2 Media Type', 'C3 Body Schema'):
        assert phrase in text
    for hidden in ('80001', '90001', '71001', '72001', 'recovery-hidden-path',
                   'explanation.', 'C1 reason', 'live demo', 'Live/ad-hoc'):
        assert hidden not in text
    assert '✗' not in text
    assert len(text.splitlines()) <= 15
    assert max(map(len, text.splitlines())) <= console.width
    assert stored == before


def test_mixed_result_compares_na_and_fails_independently(console):
    live_result.show(console, detail(reference=('FAIL', 'NOT_APPLICABLE', 'NOT_APPLICABLE'),
                                     prediction=('PASS', 'NOT_APPLICABLE', 'PASS')))
    text = console.file.getvalue()
    assert 'Reference: FNN' in text and 'Prediction: PNP' in text
    assert 'Overall: ✗ INCORRECT' in text
    rows = [line for line in text.splitlines() if any(label in line for label in live_result.LABELS)]
    assert sum('✓' in line for line in rows) == 1
    assert sum('✗' in line for line in rows) == 2
    assert 'N/A' in text


@pytest.mark.parametrize('status,heading', [
    ('parser_failure', 'Run completed'),
    ('technical_failure', 'Run failed'),
    (None, 'Run pending / interrupted'),
])
def test_failed_or_missing_output_never_becomes_semantic_prediction(console, status, heading):
    # Even stale prediction data must not turn an invalid run into a usable one.
    stored = detail(status=status)
    stored['attempts'][0]['error_kind'] = 'transport' if status == 'technical_failure' else None
    before = deepcopy(stored)
    live_result.show(console, stored)
    text = console.file.getvalue()
    assert heading in text and 'Parser: ✗ NO USABLE OUTPUT' in text
    assert 'Overall: — NO PREDICTION' in text
    assert 'Prediction: —' in text
    assert 'No prediction was inferred.' in text
    assert 'INCORRECT' not in text and 'explanation.' not in text
    rows = [line for line in text.splitlines() if any(label in line for label in live_result.LABELS)]
    assert all('✓' not in line and '✗' not in line for line in rows)
    assert stored == before


def test_missing_reference_is_unavailable_not_incorrect_or_correct(console):
    stored = detail()
    stored['reference'] = None
    live_result.show(console, stored)
    text = console.file.getvalue()
    assert 'Overall: — UNAVAILABLE' in text
    assert 'Parser: ✓ VALID' in text
    assert not live_result.correct(stored)


def test_details_expose_reasons_identifiers_paths_and_attempts(console):
    live_result.show_details(console, detail())
    text = console.file.getvalue()
    for phrase in ('Category explanations', 'Stored c1 explanation.', 'Stored c2 explanation.',
                   'Stored c3 explanation.', 'Run ID', '80001', 'Experiment ID', '90001',
                   'Attempt ID', '71001', 'Raw response file ID', '72001',
                   'Recovery directory', '/private/recovery-hidden-path'):
        assert phrase in text


def test_details_do_not_recover_reasons_from_failed_output(console):
    live_result.show_details(console, detail(status='parser_failure'))
    text = console.file.getvalue()
    assert 'No prediction was inferred.' in text
    assert 'Stored c1 explanation.' not in text
    assert '80001' in text


def test_untrusted_metadata_and_reasons_are_literal_and_controls_escaped(console):
    stored = detail(model='[red]\x1b[2J Untrusted')
    stored['prediction']['c1_reason'] = '[red]\x1b[2J' + ('x'*500)
    live_result.show_details(console, stored)
    text = console.file.getvalue()
    assert '\x1b' not in text and '\\x1b[2J' in text and '[red]' in text
    assert 'x' * 40 in text


def test_repetition_summary_counts_parser_coverage_agreement_and_correctness(console):
    records = [detail(repetition=1), detail(prediction=('PASS', 'PASS', 'FAIL'), repetition=2),
               detail(prediction=None, status='parser_failure', repetition=3)]
    live_result.repetitions(console, records)
    text = console.file.getvalue()
    assert 'Usable output 2/3 · correct 1/3 · vectors differ' in text
    assert 'Reference' in text and 'Prediction' in text
    assert '✓ CORRECT' in text and '✗ INCORRECT' in text and '✗ NO OUTPUT' in text
    assert 'NO PREDICTION' in text
    assert text.count('Repetitions') == 1
    assert 'Run completed' not in text and 'explanation.' not in text
    assert '80001' not in text and 'recovery-hidden-path' not in text
    assert len(text.splitlines()) <= 14
    assert max(map(len, text.splitlines())) <= console.width


def test_repetition_summary_separates_models_and_identical_vectors(console):
    records = [detail(model='Model A', repetition=1), detail(model='Model A', repetition=2),
               detail(model='Model B', prediction=None, status='parser_failure', repetition=1),
               detail(model='Model B', prediction=None, status='technical_failure', repetition=2)]
    live_result.repetitions(console, records)
    text = console.file.getvalue()
    assert 'Repetitions · Model A' in text and 'Repetitions · Model B' in text
    assert 'Usable output 2/2 · correct 2/2 · vectors identical' in text
    assert 'Usable output 0/2 · correct 0/2 · no usable vectors' in text


def test_single_repetition_has_no_redundant_summary(console):
    live_result.repetitions(console, [detail()])
    assert console.file.getvalue() == ''


def test_result_and_repetition_models_use_friendly_names(console):
    records = [detail(model='gemma3:27b', repetition=1), detail(model='gemma3:27b', repetition=2)]
    live_result.show(console, records[0])
    live_result.repetitions(console, records)
    text = console.file.getvalue()
    assert 'Model: Gemma 3 27B' in text
    assert 'Repetitions · Gemma 3 27B' in text
    assert 'gemma3:27b' not in text
