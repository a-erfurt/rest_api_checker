"""One reserved physical attempt at a time, with explicit recovery and retry review.

There is intentionally no study CLI or batch dispatch command in this stage.
"""
from dataclasses import asdict
from pathlib import Path

from ..persistence import spool
from .encoding import Blocked, check, digest, encode
from . import parser
from .provider import OllamaClient, Receipt, classify
from .renderer import artifact_hash as renderer_hash, render
from .request import SEEDS, build_request


class Paused(RuntimeError):
    """Preserves available receipt/spool for reconciliation; never grants retries."""
    def __init__(self, code, *, receipt=None, spool_path=None, attempt_id=None):
        super().__init__(code)
        self.receipt, self.spool_path, self.attempt_id = receipt, spool_path, attempt_id


def prepare(repo, run_id):
    inputs = repo.execution_inputs(run_id)
    run, model = inputs['run'], inputs['model']
    check(run['seed'] == SEEDS.get(run['repetition']), 'RUN_SEED_MISMATCH')
    check(inputs['setup']['parser_sha256'] == parser.artifact_hash(), 'PARSER_ARTIFACT_CHANGED')
    check(inputs['setup'].get('renderer_sha256') == renderer_hash(), 'RENDERER_ARTIFACT_CHANGED')
    rendered = render(inputs['evidence'], contract_identity=inputs['contract_identity'],
                      body_identity=inputs['body_identity'])
    request = build_request(rendered, prompt_name=inputs['prompt_name'], prompt=inputs['prompt'],
                            model=model['name'], model_digest=model['digest'], repetition=run['repetition'])
    return inputs, request


def outcome_for(receipt, *, run_id, attempt_id, request_sha256, spool_sha256,
                attempt_number, review_failure):
    """Pure classification after durable receipt. Reviewer sees technical evidence only.

    review_failure returns isolated, systematic or ambiguous; absent/uncertain
    attribution pauses. It cannot repair or override a parser outcome.
    """
    provider = classify(receipt)
    if provider.kind == 'BLOCKED':
        raise Paused(provider.code, receipt=receipt, attempt_id=attempt_id)
    diagnostics = dict(parser_sha256=parser.artifact_hash(), parser_version=parser.VERSION,
        run_id=run_id, attempt_id=attempt_id, request_sha256=request_sha256,
        spool_sha256=spool_sha256, retry_eligible=False, provider_code=provider.code,
        transport=receipt.transport, final_content=provider.content, thinking=provider.thinking,
        provider_metadata=provider.metadata)
    if provider.kind == 'TECHNICAL_FAILURE':
        attribution = review_failure(receipt, provider)
        if attribution != 'isolated':
            raise Paused('FAILURE_ATTRIBUTION_' + str(attribution), receipt=receipt, attempt_id=attempt_id)
        diagnostics.update(attribution=attribution, retry_eligible=attempt_number == 1)
        result, prediction = 'technical_failure', None
    else:
        parsed = parser.parse(provider.content)
        diagnostics['parser'] = dict(status=parsed.status, code=parsed.code, path=parsed.path)
        result = 'valid' if parsed.status == 'VALID_OUTPUT' else 'parser_failure'
        prediction = parsed.prediction
    metadata = provider.metadata if isinstance(provider.metadata, dict) else {}
    # Invalid metadata must not be rounded/coerced into DB columns. All original
    # values remain in the exact envelope and diagnostics for Gate-B inspection.
    def count(key):
        value = metadata.get(key)
        check(value is None or (type(value) is int and 0 <= value < 2**31), 'PROVIDER_COUNT_INVALID')
        return value
    done = metadata.get('done_reason')
    check(done is None or type(done) is str, 'PROVIDER_DONE_REASON_INVALID')
    return dict(result=result, prediction=prediction, diagnostics=diagnostics,
        http_status=receipt.transport.get('http_status'), done_reason=done,
        error_kind=receipt.transport.get('error_kind') or (provider.code if result=='technical_failure' else None),
        error_message=receipt.transport.get('error_message'), duration_ms=receipt.transport.get('duration_ms'),
        prompt_tokens=count('prompt_eval_count'), output_tokens=count('eval_count'),
        finished_at=receipt.received_at)


def execute_attempt(repo, run_id, *, attempt, client, spool_directory, context_proof,
                    verify_runtime, review_failure=lambda receipt, result: 'ambiguous'):
    """Future dispatch boundary; tests inject fabricated clients and evidence only.

    verify_runtime(request, proof) must establish the frozen manifest/template and
    effective runtime identity immediately before each physical attempt, including
    retries. No default implementation pretends this Gate-B evidence exists.
    """
    with repo.dispatch_owner():
        inputs, request = prepare(repo, run_id)
        context_proof.verify(request)
        # A caller must bind the measured template evidence to its frozen setup.
        proofs = inputs['setup'].get('context_proofs', {})
        check(proofs.get(str(inputs['run']['run_order'])) == asdict(context_proof), 'UNFROZEN_CONTEXT_PROOF')
        if isinstance(client, OllamaClient):
            check(inputs['setup'].get('gate_b_complete') is True
                  and inputs['setup'].get('fabricated') is not True, 'GATE_B_NOT_COMPLETE')
        check(verify_runtime(request, context_proof) is True, 'RUNTIME_IDENTITY_UNVERIFIED')
        sidecar = encode(request.metadata)
        sidecar_id = repo.archive('rendered-request-provenance.json', sidecar)
        # reserve archives exact bytes and fixes request_file_id before dispatch.
        attempt_id = repo.reserve(run_id, request.body, attempt=attempt)
        receipt, path = None, None
        try:
            with repo.provider_io(attempt_id) as observe_start:
                receipt = client.send(request, on_start=observe_start)
            check(type(receipt) is Receipt, 'PROVIDER_RECEIPT_REQUIRED')
            path = spool.stage(spool_directory, run_id=run_id, attempt_id=attempt_id,
                request_sha256=digest(request.body), setup_sha256=inputs['setup_sha256'],
                response=receipt.raw, transport={**receipt.transport,
                    'request_provenance_file_id': sidecar_id, 'request_provenance_sha256': digest(sidecar)},
                started_at=receipt.started_at, received_at=receipt.received_at)
            # Include sidecar identity through the durable spool; replay sees the
            # same augmented transport and produces byte-identical diagnostics.
            return reconcile_attempt(repo, path, review_failure=review_failure)
        except Exception as exc:
            raise Paused(str(exc), receipt=receipt, spool_path=path, attempt_id=attempt_id) from exc


def reconcile_attempt(repo, path, *, review_failure=lambda receipt, result: 'ambiguous'):
    """Never dispatch. Evidence-only import precedes deterministic adjudication.

    Settled/late/conflicting results are retained as diagnostics and cannot replace
    an outcome. An identical lost-ack replay uses repository finalization equality.
    """
    raw, value, response = spool.read(path)
    attempt = repo.attempt_state(value['attempt_id'])
    # Import bytes even when envelope attribution subsequently blocks parsing.
    spool.reconcile(repo, path)
    receipt = Receipt(response, value['transport'], value['started_at'], value['received_at'])
    try:
        outcome = outcome_for(receipt, run_id=value['run_id'], attempt_id=value['attempt_id'],
            request_sha256=value['request_sha256'], spool_sha256=digest(raw),
            attempt_number=attempt['attempt'], review_failure=review_failure)
        spool.reconcile(repo, path, outcome=outcome)
    except Exception as exc:
        raise Paused(str(exc), receipt=receipt, spool_path=Path(path), attempt_id=value['attempt_id']) from exc
    return outcome['result']
