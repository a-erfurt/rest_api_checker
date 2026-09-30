"""Bounded, byte-preserving service observations for response-case intake.

The OpenAPI snapshot supplies the operation binding. Service source is never a
contract or reference-label authority. HTTP body bytes are captured at the
application boundary, not as raw TCP/TLS traffic.
"""
from dataclasses import dataclass
from hashlib import sha256
import http.client
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from uuid import uuid4

from .persistence.database import json_bytes, require, text_bound, utc_now


RAW_PATHS = {'/edx/validation/body', '/resistance/csv/validation/body',
             '/resistance/txt/validation/body'}
FILE_PATH = '/resistance/validation/file'
ORIGINS = {'remote', 'local_original', 'controlled_variant'}
NAMESPACE = 'service-capture-v1'


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


@dataclass(frozen=True)
class ServiceTarget:
    base_url: str
    execution_origin: str
    target_id: str

    def __post_init__(self):
        require(type(self.base_url) is str and type(self.target_id) is str,
                'Service target URL and identity must be text')
        url = urlsplit(self.base_url)
        require(url.scheme in ('http', 'https') and url.hostname and url.path in ('', '/')
                and not url.query and not url.fragment and url.username is None and url.password is None,
                'Base URL must be an explicit HTTP(S) origin without credentials, path or query')
        require(self.execution_origin in ORIGINS and bool(self.target_id.strip()),
                'Explicit execution origin and target identity are required')
        try:
            port = url.port
        except ValueError as exc:
            raise ValueError('Invalid service port') from exc
        require(port is None or 1 <= port <= 65535, 'Invalid service port')


@dataclass(frozen=True)
class ServiceRequest:
    target: ServiceTarget
    path: str
    input_name: str
    input_body: bytes
    body: bytes
    headers: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class ServiceCapture:
    execution_id: str
    request: ServiceRequest
    status: int
    response_headers: tuple[tuple[str, str], ...]
    response_body: bytes
    started_at: str
    received_at: str

    @property
    def content_type(self) -> str | None:
        values = [value for name, value in self.response_headers if name.lower() == 'content-type']
        require(len(values) <= 1, 'Ambiguous response Content-Type')
        return values[0] if values else None


def _filename(name: str) -> str:
    require(bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,254}', name)) and name not in ('.', '..'),
            'Filename must be a simple ASCII basename')
    return name


def prepare(target: ServiceTarget, path: str, input_name: str, input_body: bytes,
            *, filename: str | None = None, boundary: str | None = None) -> ServiceRequest:
    require(type(input_body) is bytes, 'Exact input bytes required')
    require(path in RAW_PATHS or path == FILE_PATH, 'Unsupported validation endpoint')
    require(bool(input_name), 'Source input identity required')
    url = urlsplit(target.base_url)
    headers = [('Host', url.netloc), ('Accept', 'application/json'),
               ('Accept-Encoding', 'identity'), ('Connection', 'close')]
    if path == FILE_PATH:
        name = _filename(filename if filename is not None else Path(input_name).name)
        token = boundary or uuid4().hex
        require(bool(re.fullmatch(r'[A-Za-z0-9_-]{1,70}', token)), 'Invalid multipart boundary')
        marker = token.encode('ascii')
        require(b'\r\n--' + marker not in input_body, 'Multipart boundary collides with input')
        body = (b'--' + marker + b'\r\nContent-Disposition: form-data; name="file"; filename="'
                + name.encode('ascii') + b'"\r\nContent-Type: application/octet-stream\r\n\r\n'
                + input_body + b'\r\n--' + marker + b'--\r\n')
        headers.append(('Content-Type', f'multipart/form-data; boundary={token}'))
    else:
        require(boundary is None, 'Multipart boundary only applies to file upload')
        body = input_body
        headers.append(('Content-Type', 'application/octet-stream'))
        if filename is not None:
            require(path == '/edx/validation/body', 'Filename header is only supported for EDX raw body')
            headers.append(('filename', _filename(filename)))
    headers.append(('Content-Length', str(len(body))))
    return ServiceRequest(target, path, input_name, input_body, body, tuple(headers))


def execute(request: ServiceRequest, *, connection_factory=None, timeout=30) -> ServiceCapture:
    url = urlsplit(request.target.base_url)
    factory = connection_factory or (http.client.HTTPSConnection if url.scheme == 'https'
                                     else http.client.HTTPConnection)
    connection = factory(url.hostname, url.port, timeout=timeout)
    execution_id = str(uuid4())
    started_at = utc_now()
    try:
        connection.request('POST', request.path, body=request.body, headers=dict(request.headers))
        response = connection.getresponse()
        status = response.status
        headers = tuple(response.getheaders())
        body = response.read()  # Incomplete Content-Length raises; no case is created.
    finally:
        connection.close()
    return ServiceCapture(execution_id, request, status, headers, body, started_at, utc_now())


def check_operation(repo, contract_id: int, path: str, case_id: str):
    require(path in RAW_PATHS or path == FILE_PATH, 'Unsupported validation endpoint')
    text_bound(case_id, 64, identity=True)
    contract = repo._row('api_contracts', contract_id)
    raw = repo.file(contract['file_id'])
    document = json.loads(raw)
    require('post' in document.get('paths', {}).get(path, {}), 'POST operation absent from OpenAPI contract')
    api = repo._row('apis', contract['api_id'])
    require(repo.cn.execute('SELECT id FROM dbo.test_cases WHERE source_namespace=? AND native_case_id=?',
                            NAMESPACE, case_id).fetchone() is None, 'Case identity already exists')
    return contract, api, digest(raw)


def materialize(repo, capture: ServiceCapture, contract_id: int, case_id: str) -> dict:
    request = capture.request
    contract, api, contract_hash = check_operation(repo, contract_id, request.path, case_id)
    content_type = capture.content_type
    require(type(capture.status) is int and 100 <= capture.status <= 599, 'Invalid HTTP status')
    with repo.transaction():
        input_id = repo.archive(f'{case_id}-source-input.bin', request.input_body)
        request_id = repo.archive(f'{case_id}-request-body.bin', request.body)
        response_id_file = repo.archive(f'{case_id}-response-body.bin', capture.response_body)
        record = dict(format='service-capture-v1', case_id=case_id, api=api['name'],
                      root_family=case_id, origin='natural_observation', immediate_parent=None,
                      operation={'method': 'post', 'path': request.path}, contract_sha256=contract_hash,
                      status=capture.status, content_type=content_type,
                      body={'file_id': response_id_file, 'sha256': digest(capture.response_body),
                            'size_bytes': len(capture.response_body)},
                      execution_id=capture.execution_id, started_at=capture.started_at,
                      received_at=capture.received_at,
                      target={'base_url': request.target.base_url,
                              'execution_origin': request.target.execution_origin,
                              'target_id': request.target.target_id},
                      source_input={'name': request.input_name, 'file_id': input_id,
                                    'sha256': digest(request.input_body),
                                    'size_bytes': len(request.input_body)},
                      request={'method': 'POST', 'path': request.path,
                               'headers': list(request.headers), 'body_file_id': request_id,
                               'body_sha256': digest(request.body), 'body_size_bytes': len(request.body)},
                      response_headers=list(capture.response_headers))
        source_id = repo.archive(f'{case_id}-capture.json', json_bytes(record))
        operation_id = repo.operation(contract_id, 'post', request.path)
        family_id = repo.family(contract['api_id'], case_id)
        response_id = repo.response(capture.status, content_type, response_id_file, capture.received_at)
        case_row_id = repo.case(source_namespace=NAMESPACE, native_case_id=case_id,
                               operation_id=operation_id, response_id=response_id,
                               family_id=family_id, origin='natural_observation', parent_case_id=None,
                               source_file_id=source_id, source_pointer='')
    return dict(case_id=case_row_id, response_id=response_id, source_file_id=source_id,
                input_file_id=input_id, request_body_file_id=request_id,
                response_body_file_id=response_id_file, execution_id=capture.execution_id)
