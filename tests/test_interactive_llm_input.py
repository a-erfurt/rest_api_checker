"""Exact prepared/archived input views with fabricated transport and storage only."""
from copy import deepcopy
from decimal import Decimal
from io import StringIO
import json
from types import SimpleNamespace

import pytest
from rich.console import Console
from rich.text import Text

from rest_api_checker import interactive_llm_input as viewer, live_demo as demo, terminal
from rest_api_checker.experiment.encoding import digest, encode, loads
from rest_api_checker.experiment.provider import Receipt
from rest_api_checker.web.queries import DataUnavailable, NotFound, WebQueries
from test_live_adhoc_runtime import api_for
from test_live_demo import repository  # noqa: F401
from test_live_prompt_selection import PROMPTS, install_attempt_storage, plan, prompts  # noqa: F401


def answers(*values):
    sequence = iter(values)
    return lambda _: next(sequence)


def console():
    stream = StringIO()
    result = terminal.console(plain=True, file=stream)
    result.width = 160
    return result, stream


def payload(body='{"actual": true}', *, system=PROMPTS['P2'].decode(), **options):
    user = encode(dict(operation=dict(method='post', path='/validate'),
        openapi={'openapi': '3.0.4', 'paths': {}},
        observed_response=dict(status=201, content_type='application/json', body=body))).decode()
    return encode(dict(model='fabricated:model', messages=[dict(role='system', content=system),
        dict(role='user', content=user)], stream=False, format='json', options=options))


class Query:
    """Expose the real archive-integrity reader behind a SELECT-only fake adapter."""
    _file = WebQueries._file

    def __init__(self, raw, *, started=True):
        self.calls = []
        self.request_file_id = 5
        self.files = {}
        self.add(5, raw)
        self.attempts = [dict(request_file_id=5, started_at='2026-10-27T12:00:00Z' if started else None,
                              result='valid' if started else None)]

    def add(self, file_id, raw):
        self.files[file_id] = dict(content=raw, sha256=digest(raw), size_bytes=len(raw))

    def _one(self, sql, *params):
        assert sql.lstrip().startswith('SELECT ')
        self.calls.append((sql, params))
        if 'FROM dbo.experiment_runs' in sql:
            assert params == (77,)
            return dict(request_file_id=self.request_file_id)
        if 'FROM dbo.files' in sql:
            if params[0] not in self.files:
                raise NotFound('PRIVATE missing archive path')
            return deepcopy(self.files[params[0]])
        raise AssertionError(sql)

    def _rows(self, sql, *params):
        assert sql.lstrip().startswith('SELECT ')
        assert 'FROM dbo.run_attempts' in sql and params == (77,)
        self.calls.append((sql, params))
        return deepcopy(self.attempts)


@pytest.mark.parametrize('name,prompt_id', [('P1', 10), ('P2', 1), ('P3', 11)])
def test_preview_sent_and_archived_bytes_match_without_reference_leakage(prompts, tmp_path, monkeypatch,
                                                                       name, prompt_id):
    install_attempt_storage(prompts, monkeypatch)
    # Reference/provenance stays available to evaluation, outside the evidence DTO.
    source = json.loads(prompts.files[4])
    source.update(expected_label='GT_SENTINEL', provenance='GT_SENTINEL')
    prompts.files[4] = encode(source)
    for row in prompts.tables['reference_results'].values():
        row['notes'] = 'GT_SENTINEL'
    for row in prompts.tables['test_cases'].values():
        row['description'] = 'GT_SENTINEL'
    # A real API field with this name must not be mistaken for evaluation metadata.
    prompts.files[3] = b'{"expected_label":"actual API data", "message":"literal [red]"}'
    prompts.add('experiments', id=10003, dataset_id=3, name='Protected historical experiment')
    prompts.add('experiment_runs', id=10436, experiment_id=10003, dataset_id=3, result='valid')
    before = deepcopy(prompts.tables), dict(prompts.files)
    selected = plan(prompts, tmp_path, prompt_id, case_id=23)
    raw = selected.requests[1].body
    items = viewer.sections(raw)
    sent_payload = json.loads(raw)
    sent_user = json.loads(sent_payload['messages'][1]['content'])
    assert [label for label, _ in items] == ['Prompt', 'Recorded API Response', 'OpenAPI Contract']
    assert items[0][1] == PROMPTS[name].decode()
    metadata, body = items[1][1]
    assert body.encode() == prompts.files[3]
    assert json.loads(items[2][1]) == sent_user['openapi']
    assert json.loads(metadata) == dict(operation=sent_user['operation'], status=200,
                                        content_type=sent_user['observed_response']['content_type'])
    assert 'GT_SENTINEL' not in raw.decode()
    view, output = console()
    viewer.show_plan_input(view, selected, answers('1', '2', '3', 'q'))
    assert 'GT_SENTINEL' not in output.getvalue()
    assert 'expected_label' in output.getvalue() and 'actual API data' in output.getvalue()
    assert 'Prepared request' not in output.getvalue() and 'Request SHA-256:' not in output.getvalue()
    assert prompts.writes == [] and (prompts.tables, prompts.files) == before
    calls = []
    content = encode({key: dict(verdict='PASS', reason='FABRICATED') for key in ('c1', 'c2', 'c3')}).decode()
    receipt = Receipt(encode(dict(done=True, message=dict(role='assistant', content=content))),
        dict(complete=True, http_status=200, duration_ms=1),
        '2026-10-27T12:00:00+00:00', '2026-10-27T12:00:01+00:00')
    def send(request, *, on_start):
        calls.append(request)
        on_start(receipt.started_at)
        return receipt
    result = demo.execute(prompts, selected, root=tmp_path, spool=tmp_path/'spool',
        runtime_api=api_for(prompts), client=SimpleNamespace(send=send))
    assert result['status'] == 'COMPLETED' and len(calls) == 1
    run = prompts._row('experiment_runs', result['run_ids'][0])
    archived = prompts.file(run['request_file_id'])
    assert raw == calls[0].body == archived
    saved, _ = viewer.load_run_payload(Query(archived), 77)
    assert saved == raw and viewer.sections(saved) == items
    assert {table: {key: prompts.tables[table][key] for key in records}
            for table, records in before[0].items()} == before[0]
    assert {key: prompts.files[key] for key in before[1]} == before[1]


@pytest.mark.parametrize('started', [True, False])
def test_saved_input_is_select_only_and_distinguishes_dispatch_from_reservation(started):
    raw = payload()
    query = Query(raw, started=started)
    before = deepcopy(query.files), deepcopy(query.attempts)
    actual, source = viewer.load_run_payload(query, 77)
    assert actual == raw
    assert ('A transport start was recorded' if started else 'No transport start is recorded') in source
    if started:
        assert 'does not prove server receipt' in source
    else:
        assert 'only have been reserved' in source
    assert (query.files, query.attempts) == before
    assert all(sql.startswith('SELECT ') for sql, _ in query.calls)
    assert not any('prompts' in sql or 'reference_results' in sql for sql, _ in query.calls)


@pytest.mark.parametrize('problem', ['no_request', 'missing_file', 'hash', 'length', 'conflict', 'unsupported'])
def test_saved_input_failure_is_friendly_and_never_reconstructs(problem):
    query = Query(payload())
    if problem == 'no_request':
        query.request_file_id = None
    elif problem == 'missing_file':
        del query.files[5]
    elif problem == 'hash':
        query.files[5]['content'] = b'PRIVATE tampered bytes'
    elif problem == 'length':
        query.files[5]['size_bytes'] += 1
    elif problem == 'conflict':
        query.add(6, payload('different stored body'))
        query.attempts.append(dict(request_file_id=6, started_at=None, result=None))
    else:
        query.add(5, b'PRIVATE unsupported input')
    view, output = console()
    viewer.show_run_input(query, 77, view, answers())
    text = output.getvalue()
    assert 'No input was reconstructed' in text
    assert 'PRIVATE' not in text and 'different stored body' not in text
    assert 'Input sections' not in text


def test_archive_integrity_check_rejects_hash_tampering():
    query = Query(payload())
    query.files[5]['sha256'] = '0'*64
    with pytest.raises(DataUnavailable, match='integrity check'):
        viewer.load_run_payload(query, 77)


def test_multiple_prepared_requests_are_selected_without_mutation():
    first, second = payload('first body'), payload('second body')
    selected = SimpleNamespace(requests={1: SimpleNamespace(body=first), 2: SimpleNamespace(body=second)})
    before = deepcopy(selected)
    view, output = console()
    viewer.show_plan_input(view, selected, answers('2', '2', 'q', '1', '2', 'q', 'q'))
    assert 'second body' in output.getvalue() and 'first body' in output.getvalue()
    assert selected == before


def test_terminal_prints_full_section_without_paging_or_interpreting_markup():
    stream = StringIO()
    view = Console(file=stream, force_terminal=True, width=60, height=12, color_system='standard')
    content = '\n'.join(f'LINE-{i:02} literal [red] \x1b[2J' for i in range(12))
    viewer._show_section(view, 'Full input', content)
    text = Text.from_ansi(stream.getvalue()).plain
    for i in range(12):
        assert f'LINE-{i:02}' in text
    assert '[red]' in text and '\\x1b[2J' in text
    assert 'Page' not in text and 'From the request payload' not in text
    assert text.count('LINE-00') == 1
    assert '…' not in text


@pytest.mark.parametrize('secret', [
    {'password': 'PASSWORD_VALUE'},
    {'Authorization': 'Bearer AUTH_VALUE'},
    {'Cookie': 'session=COOKIE_VALUE'},
    {'Set-Cookie': 'session=SET_COOKIE_VALUE; HttpOnly'},
    {'nested': [{'client_secret': 'CLIENT_SECRET_VALUE'}]},
    {'token': 'TOKEN_VALUE'},
    {'x-api-key': 'APIKEY_VALUE'},
    {'detail': 'Authorization: Bearer HEADER_VALUE'},
    {'url': 'https://user:URL_PASSWORD_VALUE@example.invalid/endpoint'},
    {'private': '-----BEGIN PRIVATE KEY-----\nPEM_VALUE\n-----END PRIVATE KEY-----'},
    {'detail': 'sk-1234567890ABCDEFSECRET'},
    {'detail': 'Cookie: sid=COOKIE_VALUE; auth=COOKIE_SECOND_VALUE\nordinary response'},
    {'detail': '<response><password>XML_VALUE</password></response>'},
    {'private_key': 'PRIVATEKEY_VALUE'},
    {'aws_secret_access_key': 'AWS_SECRET_VALUE'},
    {'csrf_token': 'CSRF_VALUE'},
])
@pytest.mark.parametrize('section', ['response', 'user', 'request'])
def test_nested_secret_redaction_in_body_user_and_full_request_is_display_only(secret, section):
    body = json.dumps(dict(secret, expected_label='visible API data'))
    raw = payload(body)
    before = bytes(raw)
    label, text = viewer.sections(raw)[1]
    if section == 'user':
        text = json.loads(raw)['messages'][1]['content']
    elif section == 'request':
        text = raw.decode()
    parts = [viewer.safe_text(part) for part in (text if isinstance(text, tuple) else (text,))]
    filtered = '\n\n'.join(part for part, _ in parts)
    changed = any(redacted for _, redacted in parts)
    assert changed and '[REDACTED]' in filtered
    for token in ('PASSWORD_VALUE', 'AUTH_VALUE', 'COOKIE_VALUE', 'SET_COOKIE_VALUE', 'CLIENT_SECRET_VALUE',
                  'TOKEN_VALUE', 'APIKEY_VALUE', 'HEADER_VALUE', 'URL_PASSWORD_VALUE', 'PEM_VALUE',
                  'sk-1234567890ABCDEFSECRET', 'COOKIE_SECOND_VALUE', 'XML_VALUE', 'PRIVATEKEY_VALUE',
                  'AWS_SECRET_VALUE', 'CSRF_VALUE'):
        assert token not in filtered
    assert 'expected_label' in filtered and 'visible API data' in filtered
    view, output = console()
    viewer._show_section(view, label, text)
    assert 'Secrets redacted for display' in output.getvalue()
    assert 'sent/stored bytes are unchanged' in output.getvalue()
    assert raw == before
    assert json.loads(json.loads(raw)['messages'][1]['content'])['observed_response']['body'] == body


def test_unredacted_messages_and_secret_named_contract_properties_remain_exact():
    ordinary = 'literal [cyan]\n{"expected_label":"observed API field"}'
    assert viewer.safe_text(ordinary) == (ordinary, False)
    schema = {'type': 'object', 'properties': {
        'password': {'type': 'string', 'minLength': 12}, 'name': {'type': 'string'}},
        'required': ['password'], 'additionalProperties': False}
    contract = {'openapi': '3.0.4', 'paths': {}, 'components': {'schemas': {'Account': schema}}}
    raw = json.dumps(contract)
    assert viewer.safe_text(raw) == (raw, False)
    # An arbitrary response "properties" object is not trusted as an OpenAPI schema.
    text, changed = viewer.safe_text(json.dumps(schema))
    assert changed and json.loads(text)['properties']['password'] == '[REDACTED]'
    assert json.loads(text)['properties']['name'] == {'type': 'string'}


@pytest.mark.parametrize('keyword,value', [
    ('example', 'SCHEMA_SECRET'), ('examples', ['SCHEMA_SECRET']), ('default', 'SCHEMA_SECRET'),
    ('enum', ['SCHEMA_SECRET']), ('const', 'SCHEMA_SECRET'),
])
@pytest.mark.parametrize('section', ['contract', 'user', 'request'])
def test_secret_schema_literals_are_masked_but_contract_structure_stays_visible(keyword, value, section):
    request = json.loads(payload())
    user = json.loads(request['messages'][1]['content'])
    user['openapi']['components'] = {'schemas': {'Account': {'type': 'object',
        'properties': {'password': {'type': 'string', 'minLength': 12, keyword: value},
                       'name': {'type': 'string', 'example': 'public sample'}},
        'required': ['password'], 'additionalProperties': False}}}
    request['messages'][1]['content'] = json.dumps(user)
    raw = encode(request)
    before = bytes(raw)
    content = (viewer.sections(raw)[2][1] if section == 'contract' else
               request['messages'][1]['content'] if section == 'user' else raw.decode())
    text, changed = viewer.safe_text(content)
    assert changed and 'SCHEMA_SECRET' not in text and '[REDACTED]' in text
    assert 'password' in text and 'minLength' in text and 'required' in text
    assert 'additionalProperties' in text and 'public sample' in text
    assert raw == before and b'SCHEMA_SECRET' in raw


def test_projected_contract_preserves_decimal_precision_and_request_options_stay_unchanged():
    precise = Decimal('0.123456789012345678901234567890123456789')
    request = loads(payload(temperature=precise))
    user = loads(request['messages'][1]['content'].encode())
    user['openapi']['components'] = {'schemas': {'Bounded': {'type': 'number', 'minimum': precise}}}
    request['messages'][1]['content'] = encode(user).decode()
    raw = encode(request)
    items = viewer.sections(raw)
    assert loads(items[2][1].encode())['components']['schemas']['Bounded']['minimum'] == precise
    assert loads(raw)['options']['temperature'] == precise
    assert encode(request) == raw
    # Secret removal may reserialize JSON, but must not round unrelated numbers.
    filtered, changed = viewer.safe_text(encode({'password': 'PRIVATE', 'minimum': precise}).decode())
    assert changed and loads(filtered.encode())['minimum'] == precise


@pytest.mark.parametrize('location', ['transport', 'user', 'system', 'message'])
def test_unrecognized_metadata_or_prompt_is_rejected_instead_of_displayed(location):
    request = json.loads(payload())
    if location == 'transport':
        request['reference'] = 'GT_SENTINEL'
    elif location == 'user':
        user = json.loads(request['messages'][1]['content'])
        user['expected_label'] = 'GT_SENTINEL'
        request['messages'][1]['content'] = json.dumps(user)
    elif location == 'system':
        request['messages'][0]['content'] += '\nGT_SENTINEL'
    else:
        request['messages'][1]['reference'] = 'GT_SENTINEL'
    view, output = console()
    viewer.show_run_input(Query(encode(request)), 77, view, answers())
    assert 'No input was reconstructed' in output.getvalue()
    assert 'GT_SENTINEL' not in output.getvalue()


def test_c1_and_bidi_controls_are_escaped_without_changing_input():
    content = 'start\u009b2J\u202ehidden\u2066isolated\u2069end'
    before = content
    view, output = console()
    viewer._show_section(view, 'Controls', content)
    text = output.getvalue()
    for value in ('\u009b', '\u202e', '\u2066', '\u2069'):
        assert value not in text
        assert f'\\u{ord(value):04x}' in text
    assert content == before


def test_plain_interactive_terminal_prints_full_section_without_paging():
    class PlainTerminal(StringIO):
        def isatty(self):
            return True
    stream = PlainTerminal()
    view = Console(file=stream, force_terminal=False, width=60, height=12)
    assert not view.is_terminal
    viewer._show_section(view, 'Plain input', '\n'.join(f'LINE-{i}' for i in range(8)))
    assert 'Page' not in stream.getvalue()
    assert 'LINE-7' in stream.getvalue() and '\x1b' not in stream.getvalue()


@pytest.mark.parametrize('stored', [False, True])
def test_three_sections_return_directly_to_menu_without_extra_input(stored):
    stream = StringIO()
    view = Console(file=stream, force_terminal=True, width=80, height=12)
    body = '\n'.join(f'RESPONSE-LINE-{i:03}' for i in range(100))
    raw = payload(body)
    choices = iter(['1', '2', '3', 'q'])
    prompts = []
    def read(prompt):
        prompts.append(prompt)
        return next(choices)
    if stored:
        query = Query(raw)
        viewer.show_run_input(query, 77, view, read)
        assert query.files[5]['content'] == raw
    else:
        selected = SimpleNamespace(requests={1: SimpleNamespace(body=raw)})
        viewer.show_plan_input(view, selected, read)
        assert selected.requests[1].body == raw
    text = Text.from_ansi(stream.getvalue()).plain
    assert prompts == ['Selection [1]: ']*4
    assert text.count('Input sections') == 4
    for label in ('1  Prompt', '2  Recorded API Response', '3  OpenAPI Contract'):
        assert text.count(label) == 4
    for line in body.splitlines():
        assert text.count(line) == 1
    assert all(word in text for word in ('post', '/validate', '201', 'application/json', 'openapi'))
    for removed in ('Page', 'from user message', 'Request SHA-256', 'Request bytes',
                    'Prepared request', 'Stored request', 'System =', 'Complete user message',
                    'Complete request JSON', 'Request options', 'From the request payload',
                    'Complete messages and request included'):
        assert removed not in text
    assert text.rindex('Input sections') > text.index('RESPONSE-LINE-099')
