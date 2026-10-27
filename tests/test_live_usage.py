"""Stored provider token usage; no estimation, runtime probing or model calls."""
from contextlib import contextmanager
from copy import deepcopy
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from rest_api_checker import interactive_app, live_adhoc_runtime, live_demo_cli, live_result
from rest_api_checker import live_usage
from rest_api_checker.experiment.encoding import encode
from rest_api_checker.persistence.database import IntegrityViolation
from rest_api_checker.web.queries import DataUnavailable, NotFound
from test_live_demo_cli import args, console, core  # noqa: F401


def detail(*attempts, request_file_id=31):
    return dict(run=dict(id=77, result='valid', case='FABRICATED', model='qwen3.6:27b',
                         prompt='P2', repetition=1, request_file_id=request_file_id),
                attempts=list(attempts), reference=None, prediction=None,
                # Neither configured model capacity nor prior byte guards is a token measurement.
                runtime_evidence=dict(context_length=999999, budget_units=88888, input_tokens=77777),
                technical=dict(num_ctx=111111), usage=dict(context_limit=222222))


def attempt(number=1, input_tokens=1000, output_tokens=120, **extra):
    return dict(attempt=number, prompt_tokens=input_tokens, output_tokens=output_tokens, **extra)


def test_counts_use_latest_attempt_and_preserve_zero_without_mutation():
    stored = detail(attempt(2, 0, 0), attempt(1, 4000, 300))
    before = deepcopy(stored)
    usage = live_usage.counts(stored)
    assert usage['input_tokens'] == usage['output_tokens'] == usage['total_tokens'] == 0
    assert usage['attempt'] == 2 and usage['attempt_count'] == 2
    assert usage['context_limit'] is None and usage['input_context_percent'] is None
    assert stored == before


@pytest.mark.parametrize('reverse', [False, True])
def test_latest_missing_counts_never_fall_back_to_previous_attempt(reverse):
    attempts = [attempt(1, 4000, 300), dict(attempt=2, result=None)]
    stored = detail(*(reversed(attempts) if reverse else attempts))
    usage = live_usage.counts(stored)
    assert usage['attempt'] == 2 and usage['attempt_count'] == 2
    assert usage['input_tokens'] is usage['output_tokens'] is usage['total_tokens'] is None


@pytest.mark.parametrize('invalid', [None, True, False, -1, '123', 1.5, Decimal('123')])
@pytest.mark.parametrize('field', ['prompt_tokens', 'output_tokens'])
def test_invalid_provider_counts_are_unavailable_not_coerced(invalid, field):
    row = attempt()
    row[field] = invalid
    usage = live_usage.counts(detail(row))
    key = 'input_tokens' if field == 'prompt_tokens' else 'output_tokens'
    other = 'output_tokens' if field == 'prompt_tokens' else 'input_tokens'
    assert usage[key] is None and usage['total_tokens'] is None
    assert usage[other] == (120 if other == 'output_tokens' else 1000)


@pytest.mark.parametrize('status', ['valid', 'parser_failure', 'technical_failure', None])
def test_provider_counts_are_independent_of_parser_or_prediction_status(status):
    stored = detail(attempt(input_tokens=1280, output_tokens=64, result=status))
    stored['run']['result'] = status
    usage = live_usage.counts(stored)
    assert usage['input_tokens'] == 1280 and usage['output_tokens'] == 64
    assert usage['total_tokens'] == 1344


@pytest.mark.parametrize('stored', [dict(run={}), dict(run={}, attempts=[]), dict(run={}, attempts=None)])
def test_absent_attempts_are_unavailable(stored):
    usage = live_usage.counts(stored)
    assert usage['input_tokens'] is usage['output_tokens'] is usage['total_tokens'] is None
    assert usage['context_limit'] is None
    assert usage['attempt_count'] == 0


def test_context_comes_only_from_archived_request_and_uses_input_fraction():
    stored = detail(attempt(1, 9999, 500), attempt(2, 1024, 256))
    before = deepcopy(stored)
    reader = Mock(return_value=encode(dict(options=dict(num_ctx=32768))))
    projected = live_usage.with_usage(stored, reader)
    reader.assert_called_once_with(31)
    assert projected is not stored and projected['run'] is stored['run']
    assert projected['attempts'] is stored['attempts']
    usage = projected['usage']
    assert usage['input_tokens'] == 1024 and usage['output_tokens'] == 256
    assert usage['total_tokens'] == 1280 and usage['context_limit'] == 32768
    assert usage['input_context_percent'] == pytest.approx(3.125)
    assert stored == before


@pytest.mark.parametrize('context', [None, True, False, 0, -1, '32768', 32768.0, [], {}])
def test_invalid_context_limits_are_not_defaults_or_coerced(context):
    projected = live_usage.with_usage(detail(attempt()), lambda _: encode(dict(options=dict(num_ctx=context))))
    assert projected['usage']['context_limit'] is None
    assert projected['usage']['input_context_percent'] is None
    assert projected['usage']['total_tokens'] == 1120


@pytest.mark.parametrize('raw', [
    b'', b'not JSON containing PRIVATE_SECRET', b'\xff', b'null', b'[]', b'1',
    b'{}', b'{"options":null}', b'{"options":[]}', b'{"options":"32768"}',
    b'{"options":{"num_predict":512}}',
    b'{"options":{"num_ctx":32768,"num_ctx":4096}}',
    b'{"options":{"num_ctx":NaN}}',
])
def test_missing_or_malformed_request_never_hides_known_token_counts(raw):
    stored = detail(attempt())
    before = deepcopy(stored)
    usage = live_usage.with_usage(stored, lambda _: raw)['usage']
    assert usage['context_limit'] is None and usage['input_context_percent'] is None
    assert usage['input_tokens'] == 1000 and usage['output_tokens'] == 120
    assert stored == before


@pytest.mark.parametrize('error', [
    DataUnavailable('PRIVATE_SECRET archive is corrupt'),
    NotFound('PRIVATE_SECRET missing file'),
    IntegrityViolation('PRIVATE_SECRET wrong digest'),
    OSError('PRIVATE_SECRET archive path'),
    ValueError('PRIVATE_SECRET malformed content'),
])
def test_archive_errors_leave_usage_available_without_propagating_private_errors(error):
    reader = Mock(side_effect=error)
    projected = live_usage.with_usage(detail(attempt()), reader)
    assert projected['usage']['context_limit'] is None
    assert projected['usage']['total_tokens'] == 1120
    assert 'PRIVATE_SECRET' not in repr(projected)


@pytest.mark.parametrize('request_id', [None, False, True, 0, -1, '31', 31.0])
def test_unusable_archive_ids_do_not_trigger_a_read(request_id):
    reader = Mock(side_effect=AssertionError('No archive lookup expected'))
    usage = live_usage.with_usage(detail(attempt(), request_file_id=request_id), reader)['usage']
    reader.assert_not_called()
    assert usage['context_limit'] is None and usage['total_tokens'] == 1120


@pytest.mark.parametrize('input_tokens,expected', [(None, None), (0, 0), (65536, 200)])
def test_context_fraction_remains_unavailable_zero_or_over_capacity_truthfully(input_tokens, expected):
    usage = live_usage.with_usage(detail(attempt(input_tokens=input_tokens)),
                                  lambda _: b'{"options":{"num_ctx":32768}}')['usage']
    assert usage['context_limit'] == 32768
    assert usage['input_context_percent'] == expected


def test_browsing_enriches_detail_from_its_own_archive_reader(monkeypatch):
    stored = detail(attempt(input_tokens=2048, output_tokens=200))
    before = deepcopy(stored)
    query = SimpleNamespace(run_detail=Mock(return_value=stored),
                            _file=Mock(return_value=b'{"options":{"num_ctx":32768}}'))
    @contextmanager
    def queries(config):
        yield query
    monkeypatch.setattr(interactive_app, 'queries', queries)
    projected = interactive_app.stored_detail(object(), 77)
    query.run_detail.assert_called_once_with(77, 'reasons')
    query._file.assert_called_once_with(31)
    assert projected['usage']['context_limit'] == 32768
    assert projected['usage']['total_tokens'] == 2248
    assert stored == before


@pytest.mark.parametrize('repetitions', [1, 2])
def test_immediate_and_returned_adhoc_results_share_stored_usage(core, monkeypatch, repetitions):
    stored = detail(attempt(input_tokens=2048, output_tokens=200))
    before = deepcopy(stored)
    shown = Mock()
    monkeypatch.setattr(live_result, 'show', shown)
    monkeypatch.setattr(live_adhoc_runtime, 'probe_runtime', lambda: dict(
        available=True, version='fabricated', thesis_version='fabricated'))
    def execute(repo, plan, **kwargs):
        kwargs['notify'](dict(event='result', detail=stored))
        return dict(status='COMPLETED', exit_code=0, results=[stored])
    monkeypatch.setattr(core.module, 'execute', execute)
    options = args('--case-id', '11', '--model-id', '4', '--repetitions', str(repetitions), '--yes')
    options.adhoc = True
    view, _ = console()
    repo = SimpleNamespace(file=Mock(return_value=b'{"options":{"num_ctx":32768}}'))
    result, code = live_demo_cli.run(repo, options, view, input_fn=lambda _: pytest.fail('No input expected'),
                                   interactive=True)
    assert code == 0
    usage = result['results'][0]['usage']
    assert usage['context_limit'] == 32768 and usage['total_tokens'] == 2248
    if repetitions == 1:
        shown.assert_called_once()
        assert shown.call_args.args[1]['usage'] == usage
    else:
        shown.assert_not_called()
    assert repo.file.call_count >= 1
    assert all(call.args == (31,) for call in repo.file.call_args_list)
    assert stored == before


def test_provider_receipt_counts_reach_usage_even_when_output_parser_fails():
    from rest_api_checker.experiment.orchestration import outcome_for
    from rest_api_checker.experiment.provider import Receipt
    raw = encode(dict(done=True, prompt_eval_count=1300, eval_count=180,
        message=dict(role='assistant', content='{}')))
    receipt = Receipt(raw, dict(complete=True, http_status=200, duration_ms=1234),
                      '2026-10-27T12:00:00+00:00', '2026-10-27T12:00:01+00:00')
    outcome = outcome_for(receipt, run_id=77, attempt_id=701, request_sha256='a'*64,
        spool_sha256='b'*64, attempt_number=1,
        review_failure=lambda *unused: pytest.fail('No technical failure'))
    assert outcome['result'] == 'parser_failure'
    usage = live_usage.with_usage(detail(dict(outcome, attempt=1)),
                                  lambda _: b'{"options":{"num_ctx":32768}}')['usage']
    assert usage['input_tokens'] == 1300 and usage['output_tokens'] == 180
    assert usage['total_tokens'] == 1480
    assert usage['input_context_percent'] == pytest.approx(100*1300/32768)


def test_ambiguous_duplicate_latest_attempt_is_unavailable_not_arbitrarily_selected():
    usage = live_usage.counts(detail(attempt(2, 1, 2), attempt(2, 3, 4)))
    assert usage['input_tokens'] is usage['output_tokens'] is usage['total_tokens'] is None
    assert usage['attempt'] is None and usage['attempt_count'] == 2
