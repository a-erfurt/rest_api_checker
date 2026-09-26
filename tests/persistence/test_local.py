"""Local boundary tests; SQL behavior is tested only against SQL Server."""
from decimal import Decimal
import struct

import pytest

from rest_api_checker.persistence.database import (ConnectionSettings, IntegrityViolation,
    decimal_value, decode_datetimeoffset, pointer, text_bound, timestamp)
from rest_api_checker.persistence import spool


def test_credentials_do_not_appear_in_repr():
    assert 'secret' not in repr(ConnectionSettings(RAC_SQL_PASSWORD='secret'))


def test_lossless_timestamp_adapter():
    raw = struct.pack('<6hI2h',2026,9,26,12,13,14,123456700,0,-30)
    assert decode_datetimeoffset(raw)=='2026-09-26T12:13:14.1234567-00:30'
    for invalid in ('2026-09-26','2026-09-26T12:13:14','2026-09-26T12:13:14.12345678Z'):
        with pytest.raises(IntegrityViolation):
            timestamp(invalid)
    assert timestamp(None) is None


def test_preconversion_bounds_and_exact_decimals():
    assert text_bound('😀'*64,128)=='😀'*64
    with pytest.raises(IntegrityViolation):
        text_bound('😀'*65,128)
    assert decimal_value(Decimal('0.200'))==Decimal('0.200')
    for invalid in (0.2,Decimal('0.2000'),Decimal('NaN'),Decimal('100.000')):
        with pytest.raises(IntegrityViolation):
            decimal_value(invalid)


def test_pointer_escaping_and_missing():
    source = {'a/b':{'~': [{'':None}]}}
    assert pointer(source,'/a~1b/~0/0/') is None
    assert pointer(source,'') is source
    for invalid in ('bad','/missing','/a~2b','/a~1b/~0/01'):
        with pytest.raises(IntegrityViolation):
            pointer(source,invalid)


@pytest.mark.parametrize('response',[None,b'',b'\xff\xfe\x00',b'null',b'{broken'])
def test_spool_missing_empty_and_bytes(tmp_path,response):
    path = spool.stage(tmp_path,run_id=1,attempt_id=2,request_sha256='a'*64,setup_sha256='b'*64,
        response=response,transport={'observed':'fabricated'},received_at=None,started_at=None)
    raw,value,restored = spool.read(path)
    assert restored==response
    assert value['received_at'] is None and value['started_at'] is None
    assert path.stat().st_mode & 0o077==0
