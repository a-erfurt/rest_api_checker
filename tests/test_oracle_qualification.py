"""Literal author-approved Q01–Q26, review §3 at research commit 7e35cd2.

Bodies are the review's literal UTF-8 text with no trailing newline. Expected
vectors/labels are transcribed evidence, never generated from oracle output.
Supplemental implementation probes live in separate test modules and do not
claim human author approval or enlarge the 26-case qualification denominator.
"""
import pytest
from rest_api_checker import evaluate_response

# ID, API, actual status, Content-Type, literal raw bytes, C1/C2/C3, overall
CASES = [
    ('Q01', 'edx', 200, 'application/json', b'{}', ('PASS', 'PASS', 'PASS'), 'CONSISTENT'),
    ('Q02', 'edx', 200, 'application/json', b'{"code":500}', ('PASS', 'PASS', 'PASS'), 'CONSISTENT'),
    ('Q03', 'edx', 200, 'application/json', b'{"Code":0}', ('PASS', 'PASS', 'FAIL'), 'INCONSISTENT'),
    ('Q04', 'edx', 200, 'application/json', b'{"code":"0"}', ('PASS', 'PASS', 'FAIL'), 'INCONSISTENT'),
    ('Q05', 'edx', 200, 'application/json', b'{"code":null}', ('PASS', 'PASS', 'FAIL'), 'INCONSISTENT'),
    ('Q06', 'edx', 200, 'application/json', b'{"code":false}', ('PASS', 'PASS', 'FAIL'), 'INCONSISTENT'),
    ('Q07', 'edx', 200, 'application/json', b'{"message":null,"data":null}', ('PASS', 'PASS', 'PASS'), 'CONSISTENT'),
    ('Q08', 'edx', 200, 'application/json', b'{"data":[{"key":"a","value":"b"}]}', ('PASS', 'PASS', 'PASS'), 'CONSISTENT'),
    ('Q09', 'edx', 200, 'application/json', b'{"data":[{"key":7}]}', ('PASS', 'PASS', 'FAIL'), 'INCONSISTENT'),
    ('Q10', 'edx', 200, 'application/json', b'{"data":[{"extra":true}]}', ('PASS', 'PASS', 'FAIL'), 'INCONSISTENT'),
    ('Q11', 'htts', 200, 'application/json', b'null', ('PASS', 'PASS', 'PASS'), 'CONSISTENT'),
    ('Q12', 'htts', 200, 'application/json', b'[1,"x"]', ('PASS', 'PASS', 'PASS'), 'CONSISTENT'),
    ('Q13', 'htts', 200, 'application/json', b'{broken', ('PASS', 'PASS', 'FAIL'), 'INCONSISTENT'),
    ('Q14', 'htts', 422, 'application/json', b'{"detail":[{"loc":["body","file"],"msg":"Field required","type":"missing","input":null}]}', ('PASS', 'PASS', 'PASS'), 'CONSISTENT'),
    ('Q15', 'htts', 422, 'application/json', b'{}', ('PASS', 'PASS', 'PASS'), 'CONSISTENT'),
    ('Q16', 'htts', 422, 'application/json', b'{"detail":[]}', ('PASS', 'PASS', 'PASS'), 'CONSISTENT'),
    ('Q17', 'htts', 422, 'application/json', b'{"detail":[{"loc":[],"type":"missing"}]}', ('PASS', 'PASS', 'FAIL'), 'INCONSISTENT'),
    ('Q18', 'htts', 422, 'application/json', b'{"detail":[{"loc":"file","msg":"x","type":"x"}]}', ('PASS', 'PASS', 'FAIL'), 'INCONSISTENT'),
    ('Q19', 'htts', 422, 'application/json', b'{"detail":null}', ('PASS', 'PASS', 'FAIL'), 'INCONSISTENT'),
    ('Q20', 'htts', 422, 'application/json', b'{"detail":[{"loc":[0],"msg":"x","type":"x","extra":1}],"extra":true}', ('PASS', 'PASS', 'PASS'), 'CONSISTENT'),
    ('Q21', 'htts', 422, 'application/json', b'{"detail":123}', ('PASS', 'PASS', 'FAIL'), 'INCONSISTENT'),
    ('Q22', 'htts', 200, 'application/json', b'{"detail":123}', ('PASS', 'PASS', 'PASS'), 'CONSISTENT'),
    ('Q23', 'edx', 200, 'application/xml', b'{}', ('PASS', 'FAIL', 'NOT_APPLICABLE'), 'INCONSISTENT'),
    ('Q24', 'htts', 200, 'text/plain', b'{}', ('PASS', 'FAIL', 'NOT_APPLICABLE'), 'INCONSISTENT'),
    ('Q25', 'htts', 500, 'application/json', b'{}', ('FAIL', 'NOT_APPLICABLE', 'NOT_APPLICABLE'), 'INCONSISTENT'),
    ('Q26', 'edx', 200, 'application/json; charset=utf-8', b'{"code":0}', ('PASS', 'PASS', 'PASS'), 'CONSISTENT'),
]


@pytest.mark.parametrize('qid,api,status,media,body,vector,overall', CASES, ids=[c[0] for c in CASES])
def test_author_approved_qualification(contracts, operations, qid, api, status, media, body, vector, overall):
    result = evaluate_response(contracts[api], operations[api], 'post', status, media, body)
    assert result.vector == vector
    assert result.overall == overall
    assert result.selected_response == (None if qid == 'Q25' else str(status))
    assert result.selected_media == (None if qid in {'Q23', 'Q24', 'Q25'} else 'application/json')
    if qid == 'Q13':
        assert result.diagnostics[0].code == 'INVALID_JSON_REPRESENTATION'
    if qid == 'Q25':
        assert result.diagnostics[0].code == 'UNDOCUMENTED_STATUS'


def test_qualification_inventory():
    assert [c[0] for c in CASES] == [f'Q{i:02}' for i in range(1, 27)]
    assert sum(c[-1] == 'CONSISTENT' for c in CASES) == 12
    assert sum(c[-1] == 'INCONSISTENT' for c in CASES) == 14
