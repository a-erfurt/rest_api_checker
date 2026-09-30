"""Controlled HTTP and repository doubles; no service or SQL Server required."""
from contextlib import contextmanager
from hashlib import sha256
import json

import pytest

from rest_api_checker.cli import arguments
from rest_api_checker.persistence.database import IntegrityViolation, json_bytes
from rest_api_checker import service_capture as sc


class FakeResponse:
    status = 207

    def getheaders(self):
        return [('Content-Type', 'application/json; charset=utf-8'), ('X-Trace', 'abc')]

    def read(self):
        return b'\xff\x00{\r\n'


class FakeConnection:
    calls = []

    def __init__(self, host, port, *, timeout):
        self.calls.append(('connect', host, port, timeout))

    def request(self, method, path, *, body, headers):
        self.calls.append(('request', method, path, body, headers))

    def getresponse(self):
        return FakeResponse()

    def close(self):
        self.calls.append(('close',))


def target(base='http://localhost:5034', origin='local_original'):
    return sc.ServiceTarget(base, origin, 'source-commit-123')


def test_explicit_target_configuration_and_rejections():
    assert target().base_url == 'http://localhost:5034'
    assert target('http://127.0.0.1:8001').base_url == 'http://127.0.0.1:8001'
    assert target('https://controlled.example:8443', 'controlled_variant').execution_origin == 'controlled_variant'
    for bad in ('localhost:5034', 'http://localhost:5034/prefix',
                'http://user:secret@localhost:5034', 'http://localhost:5034/?x=1'):
        with pytest.raises(IntegrityViolation):
            target(bad)
    with pytest.raises(IntegrityViolation):
        sc.ServiceTarget('http://localhost:5034', 'unknown', 'x')


def test_cli_requires_explicit_target_and_input():
    base = ['service', 'capture', '--contract-id', '1', '--path', '/edx/validation/body',
            '--input', 'sample.csv', '--case-id', 'CAPTURE-1']
    with pytest.raises(SystemExit):
        arguments().parse_args(base)
    args = arguments().parse_args(base + ['--base-url', 'http://localhost:5034',
                                          '--execution-origin', 'local_original',
                                          '--target-id', 'source-commit-123'])
    assert args.base_url == 'http://localhost:5034'
    assert args.execution_origin == 'local_original'


@pytest.mark.parametrize('path', sorted(sc.RAW_PATHS))
def test_raw_input_is_identical_to_request_body(path):
    raw = b'\x00\xff\r\nlast,field'  # no terminal newline; never decoded or normalized
    request = sc.prepare(target(), path, 'input.csv', raw, filename='input.csv' if path.startswith('/edx/') else None)
    assert request.body is raw
    assert request.input_body is raw
    assert dict(request.headers)['Content-Length'] == str(len(raw))
    assert dict(request.headers)['Content-Type'] == 'application/octet-stream'
    assert (('filename', 'input.csv') in request.headers) == path.startswith('/edx/')


def test_multipart_contains_exact_input_once_and_preserves_full_sent_body():
    raw = b'alpha\r\nbeta\x00\xff'
    request = sc.prepare(target('http://127.0.0.1:8001'), sc.FILE_PATH,
                         '/source/specimen.csv', raw, boundary='bounded123')
    assert request.body.count(raw) == 1
    assert request.body.startswith(b'--bounded123\r\nContent-Disposition: form-data; name="file"; filename="specimen.csv"')
    assert request.body.endswith(raw + b'\r\n--bounded123--\r\n')
    assert dict(request.headers)['Content-Type'] == 'multipart/form-data; boundary=bounded123'
    assert dict(request.headers)['Content-Length'] == str(len(request.body))
    with pytest.raises(IntegrityViolation):
        sc.prepare(target(), sc.FILE_PATH, 'x.csv', b'\r\n--bounded123', boundary='bounded123')


def test_http_request_metadata_and_exact_response_bytes():
    FakeConnection.calls = []
    request = sc.prepare(target(), '/edx/validation/body', 'x.csv', b'\xef\xbb\xbf\x00', filename='x.csv')
    result = sc.execute(request, connection_factory=FakeConnection)
    assert FakeConnection.calls[0] == ('connect', 'localhost', 5034, 30)
    assert FakeConnection.calls[1] == ('request', 'POST', '/edx/validation/body', request.body, dict(request.headers))
    assert FakeConnection.calls[2] == ('close',)
    assert result.status == 207
    assert result.content_type == 'application/json; charset=utf-8'
    assert result.response_body == b'\xff\x00{\r\n'
    assert result.response_headers == (('Content-Type', 'application/json; charset=utf-8'), ('X-Trace', 'abc'))
    assert result.execution_id and result.started_at and result.received_at


class FakeCursor:
    def fetchone(self):
        return None


class FakeDatabase:
    def execute(self, *_args):
        return FakeCursor()


class FakeRepo:
    def __init__(self):
        self.cn = FakeDatabase()
        self.raw_contract = json_bytes({'openapi': '3.1.0', 'paths': {sc.FILE_PATH: {'post': {}}}})
        self.files = {10: self.raw_contract}
        self.rows = {'api_contracts': {1: {'id': 1, 'api_id': 2, 'file_id': 10}},
                     'apis': {2: {'id': 2, 'name': 'resistance'}}}
        self.calls = []

    def _row(self, table, row_id):
        return self.rows[table][row_id]

    def file(self, file_id):
        return self.files[file_id]

    @contextmanager
    def transaction(self):
        yield self

    def archive(self, name, raw):
        file_id = max(self.files) + 1
        self.files[file_id] = raw
        self.calls.append(('archive', name, file_id))
        return file_id

    def operation(self, contract_id, method, path):
        assert (contract_id, method, path) == (1, 'post', sc.FILE_PATH)
        return 20

    def family(self, api_id, code):
        assert (api_id, code) == (2, 'OBS-1')
        return 21

    def response(self, status, content_type, body_file_id, observed_at):
        assert status == 207 and content_type == 'application/json; charset=utf-8'
        assert self.files[body_file_id] == b'\xff\x00{\r\n'
        assert observed_at
        return 22

    def case(self, **fields):
        assert fields['operation_id'] == 20 and fields['response_id'] == 22
        assert fields['origin'] == 'natural_observation' and fields['parent_case_id'] is None
        assert fields['source_namespace'] == sc.NAMESPACE and fields['source_pointer'] == ''
        record = json.loads(self.files[fields['source_file_id']])
        assert record['case_id'] == fields['native_case_id']
        assert record['root_family'] == 'OBS-1'
        assert record['operation'] == {'method': 'post', 'path': sc.FILE_PATH}
        assert record['contract_sha256'] == sha256(self.raw_contract).hexdigest()
        assert record['body']['sha256'] == sha256(b'\xff\x00{\r\n').hexdigest()
        assert record['target']['execution_origin'] == 'local_original'
        assert record['target']['base_url'] == 'http://127.0.0.1:8001'
        assert record['source_input']['sha256'] == sha256(b'a\xff\r\n').hexdigest()
        assert self.files[record['source_input']['file_id']] == b'a\xff\r\n'
        assert self.files[record['request']['body_file_id']] == self.expected_request.body
        assert record['response_headers'] == [['Content-Type', 'application/json; charset=utf-8'], ['X-Trace', 'abc']]
        assert 'oracle' not in record and 'reference' not in record
        return 23


def test_materialization_binds_input_request_response_case_without_label():
    request = sc.prepare(target('http://127.0.0.1:8001'), sc.FILE_PATH, 'specimen.csv',
                         b'a\xff\r\n', boundary='bounded123')
    capture = sc.execute(request, connection_factory=FakeConnection)
    repo = FakeRepo()
    repo.expected_request = request
    result = sc.materialize(repo, capture, 1, 'OBS-1')
    assert result['case_id'] == 23 and result['response_id'] == 22
    assert not any(call[0] == 'reference' for call in repo.calls)


def test_contract_path_rejected_before_execution():
    repo = FakeRepo()
    with pytest.raises(IntegrityViolation, match='absent from OpenAPI'):
        sc.check_operation(repo, 1, '/edx/validation/body', 'OBS-1')
    assert repo.calls == []
