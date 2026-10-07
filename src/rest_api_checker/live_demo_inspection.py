"""Read persisted run evidence without reconstructing or executing a request."""
import base64
import json

from .persistence import inspection


def run_detail(repo, run_id, *, raw=False):
    """Keep the authoritative comparison projection; add stored bytes on request."""
    result = inspection.run_detail(repo, run_id, raw=False)
    if raw:
        request_id = result['run']['request_file_id']
        request = json.loads(repo.file(request_id)) if request_id is not None else None
        messages = request.get('messages', []) if isinstance(request, dict) else []
        evidence = next((message.get('content') for message in messages
                         if isinstance(message, dict) and message.get('role') == 'user'), None)
        result['raw'] = dict(request=request, evidence=evidence,
            provider_envelopes=[dict(attempt=attempt['attempt'], base64=base64.b64encode(
                repo.file(attempt['response_file_id'])).decode())
                for attempt in result['attempts'] if attempt['response_file_id'] is not None])
    return result
