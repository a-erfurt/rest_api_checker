"""Explicit connections and lossless driver adapters. Never auto-migrates."""
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import re
import struct

import pyodbc

# Explicit connection lifetime is essential for safe disposable database cleanup.
pyodbc.pooling = False


class ConnectionSettings(dict):
    def __repr__(self):
        return 'ConnectionSettings(<redacted>)'


class IntegrityViolation(ValueError):
    """Source, identity or lifecycle mismatch; never silently repair evidence."""


def require(condition, message):
    if not condition:
        raise IntegrityViolation(message)


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


def timestamp(value):
    if value is None:
        return None
    require(isinstance(value, str) and re.fullmatch(
        r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,7})?(?:Z|[+-]\d{2}:\d{2})', value),
        'A genuinely observed offset-qualified timestamp with at most 7 fractional digits is required')
    datetime.fromisoformat(value)  # Validate calendar and offset without reserializing.
    return value


def decode_datetimeoffset(raw):
    year, month, day, hour, minute, second, nanos, tz_hour, tz_minute = struct.unpack('<6hI2h', raw)
    require(nanos % 100 == 0, 'Unrepresentable timestamp precision')
    offset = tz_hour * 60 + tz_minute
    return (f'{year:04}-{month:02}-{day:02}T{hour:02}:{minute:02}:{second:02}.'
            f'{nanos // 100:07}{"+" if offset >= 0 else "-"}{abs(offset)//60:02}:{abs(offset)%60:02}')


def text_bound(value, width=None, *, ascii_only=False, identity=False, empty=False):
    require(type(value) is str, 'Expected text, not coercion')
    encoded = value.encode('ascii' if ascii_only else 'utf-16-le')
    limit = (width if ascii_only else width * 2) if width else 2**31 - 1
    require(len(encoded) <= limit, f'Text exceeds storage bound: {len(encoded)} bytes > {limit}')
    if identity:
        require((empty or bool(value)) and not value.endswith(' '), 'Empty or trailing-space identity')
    return value


def integer(value, bits=64, minimum=None):
    require(type(value) is int and -(2**(bits-1)) <= value < 2**(bits-1), 'Integer outside storage bound')
    require(minimum is None or value >= minimum, 'Integer below minimum')
    return value


def decimal_value(value, precision=5, scale=3):
    require(isinstance(value, Decimal) and value.is_finite(), 'Use an exact finite Decimal')
    require(value.as_tuple().exponent >= -scale and abs(value) < Decimal(10)**(precision-scale),
            'Decimal excess scale/precision; SQL rounding is forbidden')
    return value


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def pointer(document, path):
    require(type(path) is str and (path == '' or path.startswith('/')), 'Invalid JSON Pointer')
    node = document
    for segment in path.split('/')[1:] if path else []:
        require(re.search(r'~(?![01])', segment) is None, 'Invalid JSON Pointer escape')
        segment = segment.replace('~1', '/').replace('~0', '~')
        try:
            if isinstance(node, list):
                require(bool(re.fullmatch(r'0|[1-9][0-9]*', segment)), 'Invalid array pointer')
                node = node[int(segment)]
            else:
                node = node[segment]
        except (KeyError, IndexError, TypeError) as exc:
            raise IntegrityViolation('Missing source pointer') from exc
    return node


def read_settings(path):
    path = Path(path)
    require(path.stat().st_mode & 0o077 == 0, 'Credentials must be private (0600)')
    settings = dict(line.split('=', 1) for line in path.read_text().splitlines() if line and not line.startswith('#'))
    require({'RAC_SQL_PASSWORD', 'RAC_SQL_PORT'} <= settings.keys(), 'Missing connection settings')
    integer(int(settings['RAC_SQL_PORT']), 32, 1024)
    require(int(settings['RAC_SQL_PORT']) <= 65535, 'Invalid port')
    return ConnectionSettings(settings)


def database_name(name):
    require(bool(re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,127}', name)), 'Unsafe database name')
    return name


def connect(settings, database, *, autocommit=False):
    database_name(database)
    def quote(value):
        return '{' + str(value).replace('}', '}}') + '}'
    cn = pyodbc.connect(
        'DRIVER={ODBC Driver 18 for SQL Server};SERVER=tcp:127.0.0.1,' + str(settings['RAC_SQL_PORT'])
        + ';DATABASE=' + quote(database) + ';UID=' + quote(settings.get('RAC_SQL_USER', 'sa'))
        + ';PWD=' + quote(settings['RAC_SQL_PASSWORD'])
        + ';Encrypt=yes;TrustServerCertificate=yes;LongAsMax=yes;APP=RestApiCheckerPersistence;',
        autocommit=autocommit, timeout=10)
    cn.timeout = 60
    cn.add_output_converter(-155, decode_datetimeoffset)
    cn.execute('SET XACT_ABORT ON; SET ANSI_WARNINGS ON; SET NOCOUNT ON;')
    return cn


@contextmanager
def transaction(cn):
    """Only for an exclusively owned connection; rollback on all failures."""
    require(not cn.autocommit, 'Transactions require autocommit=False')
    try:
        yield cn
        cn.commit()
    except BaseException:
        cn.rollback()
        raise


def lock(cn, resource, timeout_ms=10000):
    require(len(resource) <= 255, 'Lock identity too long')
    # BEGIN is explicit because sp_getapplock itself does not start an ODBC transaction.
    cn.execute('IF @@TRANCOUNT=0 BEGIN TRANSACTION;')
    result = cn.execute("""DECLARE @r INT;
        EXEC @r=sys.sp_getapplock @Resource=?, @LockMode='Exclusive',
             @LockOwner='Transaction', @LockTimeout=?; SELECT @r;""", resource, timeout_ms).fetchval()
    require(result >= 0, f'Exclusive lock failed ({result})')
