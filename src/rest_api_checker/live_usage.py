"""Read-only token usage from stored attempts and the archived request limit."""
import pyodbc

from .experiment.encoding import loads
from .web.queries import DataUnavailable


def _count(value):
    # Missing/invalid telemetry is unknown. Zero is a legitimate provider count.
    return value if type(value) is int and value >= 0 else None


def counts(detail):
    """Use the latest physical attempt, never sum retries or reuse earlier counts."""
    attempts = detail.get('attempts') or []
    latest = {}
    if attempts and all(isinstance(a, dict) and type(a.get('attempt')) is int
                        and a['attempt'] > 0 for a in attempts):
        number = max(a['attempt'] for a in attempts)
        matching = [a for a in attempts if a['attempt'] == number]
        if len(matching) == 1:
            latest = matching[0]
    input_tokens, output_tokens = (_count(latest.get(key)) for key in ('prompt_tokens', 'output_tokens'))
    return dict(input_tokens=input_tokens, output_tokens=output_tokens,
        total_tokens=input_tokens+output_tokens if input_tokens is not None and output_tokens is not None else None,
        attempt=latest.get('attempt'), attempt_count=len(attempts), context_limit=None,
        input_context_percent=None)


def with_usage(detail, read_file):
    """Add presentation data without rebuilding requests or reading current config.

    The supplied archive reader must perform its existing hash/length check.
    A missing or damaged request makes only the requested context limit unknown;
    known token counts remain usable. Never expose reader/JSON exception text.
    """
    usage = counts(detail)
    file_id = detail['run'].get('request_file_id')
    if type(file_id) is int and file_id > 0:
        try:
            request = loads(read_file(file_id))
            options = request.get('options') if isinstance(request, dict) else None
            limit = _count(options.get('num_ctx')) if isinstance(options, dict) else None
            if limit:
                usage['context_limit'] = limit
                if usage['input_tokens'] is not None:
                    usage['input_context_percent'] = 100 * usage['input_tokens'] / limit
        except (DataUnavailable, LookupError, ValueError, TypeError, OSError, pyodbc.Error, RecursionError):
            pass
    return dict(detail, usage=usage)
