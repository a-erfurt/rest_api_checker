"""Opt-in disposable SQL round trip for service observations."""
from hashlib import sha256
import json

import pytest

from rest_api_checker.persistence.database import json_bytes
from rest_api_checker.service_capture import (FILE_PATH, ServiceCapture, ServiceTarget,
                                               materialize, prepare)


@pytest.mark.sqlserver
def test_service_capture_sql_round_trip_without_reference(repo):
    api_id = repo.api('service-capture-fixture')
    raw_contract = json_bytes({'openapi': '3.1.0', 'paths': {FILE_PATH: {'post': {'responses': {'200': {}}}}}})
    contract_id = repo.contract(api_id, repo.archive('capture-contract.json', raw_contract), '3.1.0')
    source = b'\x00sample\r\n\xff'
    request = prepare(ServiceTarget('http://127.0.0.1:8001', 'local_original', 'fixture-source-commit'),
                      FILE_PATH, 'input.csv', source, boundary='fixtureBoundary')
    body = b'\xff{\r\n'
    capture = ServiceCapture('fixture-execution', request, 200,
                             (('Content-Type', 'application/json'), ('X-Test', 'preserved')),
                             body, '2026-10-01T12:00:00+00:00', '2026-10-01T12:00:01+00:00')
    result = materialize(repo, capture, contract_id, 'CAPTURE-1')
    case = repo._row('test_cases', result['case_id'])
    response = repo._row('responses', case['response_id'])
    manifest = json.loads(repo.file(case['source_file_id']))
    assert case['operation_id'] == repo.operation(contract_id, 'post', FILE_PATH)
    assert response['status_code'] == 200 and response['content_type'] == 'application/json'
    assert repo.file(response['body_file_id']) == body
    assert repo.file(manifest['source_input']['file_id']) == source
    assert repo.file(manifest['request']['body_file_id']) == request.body
    assert manifest['source_input']['sha256'] == sha256(source).hexdigest()
    assert manifest['response_headers'] == [['Content-Type', 'application/json'], ['X-Test', 'preserved']]
    assert repo.cn.execute('SELECT COUNT(*) FROM dbo.reference_results WHERE case_id=?',
                           result['case_id']).fetchval() == 0
