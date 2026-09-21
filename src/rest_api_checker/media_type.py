"""Bounded media matching; only the protocol's JSON charset form is admitted."""
import re
from collections.abc import Mapping

from .models import OracleNotReady

_TOKEN = r"[!#$%&'*+.^_`|~0-9A-Za-z-]+"
_BASE = re.compile(rf'({_TOKEN})/({_TOKEN})')
_CHARSET = re.compile(r'charset=utf-8', re.IGNORECASE)


def parse_media_type(value: str | None) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OracleNotReady('MISSING_CONTENT_TYPE')
    if '\r' in value or '\n' in value or ',' in value:
        raise OracleNotReady('AMBIGUOUS_CONTENT_TYPE')
    parts = value.strip(' \t').split(';')
    base = parts[0].strip(' \t').lower()
    if not _BASE.fullmatch(base) or '*' in base:
        raise OracleNotReady('MALFORMED_CONTENT_TYPE')
    if len(parts) > 1 and not (
        base == 'application/json' and len(parts) == 2
        and _CHARSET.fullmatch(parts[1].strip(' \t'))
    ):
        raise OracleNotReady('UNQUALIFIED_MEDIA_PARAMETERS')
    return base


def select_media(content: Mapping, observed: str | None) -> str | None:
    """Return the original declared key; None is a valid media mismatch."""
    base = parse_media_type(observed)
    keys = {}
    for key in content:
        if not isinstance(key, str) or ';' in key or '*' in key:
            raise OracleNotReady('UNSUPPORTED_MEDIA_DECLARATION', str(key))
        normalized = parse_media_type(key)
        if normalized in keys:
            raise OracleNotReady('AMBIGUOUS_MEDIA_DECLARATION', key)
        keys[normalized] = key
    return keys.get(base)
