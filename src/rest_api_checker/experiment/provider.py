"""One-shot Ollama HTTP transport and conservative envelope attribution.

No SDK defaults, redirects, HTTP retries, JSON mode or model loading probes.
"""
from dataclasses import dataclass
import http.client
import json
import socket
import threading
import time
from urllib.parse import urlsplit

from ..persistence.database import utc_now
from .encoding import check, invalid_constant, unique_object
from .request import TIMEOUT, validate_request


@dataclass(frozen=True, slots=True)
class Receipt:
    raw: bytes | None
    transport: dict
    started_at: str
    received_at: str


class OllamaClient:
    """One new connection/request per call. A total deadline bounds reads as well."""
    def __init__(self, endpoint='http://127.0.0.1:11434/api/chat', *, connection_factory=None,
                 request_validator=validate_request):
        target = urlsplit(endpoint)
        check(target.scheme in ('http', 'https') and target.path == '/api/chat'
              and target.hostname and not target.query and not target.fragment
              and target.username is None and target.password is None, 'INVALID_OLLAMA_ENDPOINT')
        self.target = target
        self.request_validator = request_validator
        self.factory = connection_factory or (http.client.HTTPSConnection if target.scheme == 'https'
                                               else http.client.HTTPConnection)

    def send(self, request, *, on_start):
        self.request_validator(request)
        connection = self.factory(self.target.hostname, self.target.port, timeout=TIMEOUT)
        started_at = utc_now()
        # Commit the observed dispatch boundary before entering HTTP. If it fails,
        # no send occurs; reservation still requires reconciliation, never takeover.
        on_start(started_at)
        start = time.monotonic()
        deadline = start + TIMEOUT
        raw, status, headers = bytearray(), None, []
        wire_socket = None

        def expire():
            # A trickling peer must not extend a 300-second attempt by resetting
            # per-read socket timeouts. Shutdown unblocks headers/body reads.
            if wire_socket is not None:
                try:
                    wire_socket.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
        watchdog = threading.Timer(TIMEOUT, expire)
        watchdog.daemon = True

        def remaining():
            seconds = deadline - time.monotonic()
            if seconds <= 0:
                raise TimeoutError('per-attempt deadline')
            if wire_socket is not None:
                wire_socket.settimeout(seconds)

        try:
            watchdog.start()
            connection.connect()
            wire_socket = connection.sock
            remaining()
            connection.request('POST', '/api/chat', body=request.body,
                               headers={'Content-Type': 'application/json', 'Accept': 'application/json'})
            remaining()
            response = connection.getresponse()
            status, headers = response.status, response.getheaders()
            while True:
                remaining()
                chunk = response.read1(65536)
                if time.monotonic() >= deadline:
                    raw.extend(chunk)
                    raise TimeoutError('per-attempt deadline')
                if not chunk:
                    break
                raw.extend(chunk)
                if response.length == 0:
                    break  # read1 may have closed a Connection: close socket.
            if response.length not in (None, 0):
                raise ConnectionError('incomplete HTTP response body')
            transport = dict(complete=True, error_kind=None, error_message=None)
        except (TimeoutError, socket.timeout) as exc:
            transport = dict(complete=False, error_kind='timeout', error_message=str(exc))
        except (ConnectionError, OSError, http.client.HTTPException) as exc:
            if isinstance(exc, http.client.IncompleteRead) and exc.partial:
                raw.extend(exc.partial)
            transport = dict(complete=False, error_kind='timeout' if time.monotonic() >= deadline else 'transport',
                             error_message=str(exc))
        finally:
            watchdog.cancel()
            connection.close()
        transport.update(http_status=status, headers=headers,
                         duration_ms=int((time.monotonic() - start) * 1000))
        return Receipt(bytes(raw) if raw or status is not None else None, transport,
                       started_at, utc_now())


@dataclass(frozen=True, slots=True)
class ProviderResult:
    kind: str  # FINAL, TECHNICAL_FAILURE, BLOCKED; parser owns output validity.
    code: str
    content: str | None = None
    thinking: str | None = None
    metadata: dict | None = None


def classify(receipt: Receipt) -> ProviderResult:
    transport = receipt.transport
    if transport.get('complete') is False and transport.get('error_kind') in ('timeout', 'transport'):
        return ProviderResult('TECHNICAL_FAILURE', transport['error_kind'])
    if transport.get('complete') is not True:
        return ProviderResult('BLOCKED', 'AMBIGUOUS_TRANSPORT')
    status = transport.get('http_status')
    try:
        envelope = json.loads(receipt.raw.decode('utf-8'), object_pairs_hook=unique_object,
                              parse_constant=invalid_constant)
    except (ValueError, UnicodeError, AttributeError, RecursionError):
        envelope = None
    if type(status) is int and 500 <= status <= 599:
        # Explicit server-side failure, subject to isolated/systematic review.
        return ProviderResult('TECHNICAL_FAILURE', 'HTTP_SERVER_FAILURE', metadata=envelope)
    if status != 200:
        return ProviderResult('BLOCKED', 'HTTP_CONFIGURATION_OR_AMBIGUOUS_FAILURE', metadata=envelope)
    if not isinstance(envelope, dict):
        return ProviderResult('BLOCKED', 'UNUSABLE_ENVELOPE_WITHOUT_RUNTIME_ATTRIBUTION')
    if envelope.get('error'):
        # Arbitrary error text is not sufficient to infer crash/OOM entitlement.
        return ProviderResult('BLOCKED', 'RUNTIME_ERROR_REQUIRES_ATTRIBUTION', metadata=envelope)
    message = envelope.get('message')
    if (envelope.get('done') is not True or not isinstance(message, dict)
            or message.get('role') != 'assistant' or type(message.get('content')) is not str
            or ('thinking' in message and type(message['thinking']) is not str)):
        return ProviderResult('BLOCKED', 'INCOMPLETE_OR_AMBIGUOUS_ENVELOPE', metadata=envelope)
    if message.get('tool_calls') or message.get('images'):
        return ProviderResult('BLOCKED', 'UNREQUESTED_PROVIDER_MODE', metadata=envelope)
    # Empty content is a designated final answer; missing content above is not.
    return ProviderResult('FINAL', 'COMPLETE_FINAL_CONTENT', message['content'],
                          message.get('thinking'), envelope)
