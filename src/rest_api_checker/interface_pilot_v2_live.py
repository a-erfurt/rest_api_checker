"""Single-use dispatch of an exact, development-only 18-request interface pilot."""
import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import uuid

from . import freeze, interface_pilot_v2 as preparer, runtime_evidence
from .experiment import parser, provider, request_v2
from .experiment.encoding import check, digest, encode, loads
from .experiment.request import ContextProof, MODELS
from .persistence.database import utc_now

ENDPOINT = 'http://127.0.0.1:11434/api/chat'


def publish(path, raw):
    """Exclusive, fsynced evidence; a failed write leaves bytes for manual review."""
    path = Path(path)
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def load_prepared(directory, cases, model_digests, *, root, research):
    """Revalidate released DEV metadata and every prepared byte, then retain bytes.

    Reconstruction verifies equality only: the loaded request is what is sent.
    No caller-selectable dataset, source contract, repetition or output mode.
    """
    directory = Path(directory).resolve()
    expected = preparer.pilot_files(cases, model_digests, root=root, research=research)
    files = {name: (directory/name).read_bytes() for name in expected}
    check(files == expected, 'PREPARED_PILOT_BYTES_CHANGED')
    plan = loads(files['manifest.json'])
    requests = [(slot, request_v2.RequestV2(files[slot['request_path']],
                 loads(files[slot['provenance_path']]))) for slot in plan['slots']]
    for _, request in requests:
        request_v2.validate_request_v2(request)
    return plan, files, requests


def verify_bindings(binding, proofs, requests, *, root):
    """Use existing runtime identities and exact-request native context evidence."""
    check(type(binding) is dict and set(binding) == {'runtime', 'models'},
          'EXPLICIT_RUNTIME_AND_MODEL_BINDINGS_REQUIRED')
    identities = binding['models']
    check(type(identities) is list and [i['name'] for i in identities] == list(MODELS),
          'EXACT_THREE_OLLAMA_MODELS_REQUIRED')
    check(type(proofs) is dict and set(proofs) == {digest(r.body) for _, r in requests},
          'EXACT_18_REQUEST_CONTEXT_PROOFS_REQUIRED')
    by_model = {i['name']: i for i in identities}
    native_metadata = {}
    for identity in identities:
        name = Path(identity['show'])
        check(not name.is_absolute() and '..' not in name.parts, 'UNSAFE_NATIVE_METADATA_PATH')
        raw = (Path(root)/runtime_evidence.DIRECTORY/name).read_bytes()
        native_metadata[str(name)] = raw
        show = json.loads(raw)
        check(digest(show['template'].encode('utf-8')) == identity['template_sha256'],
              'NATIVE_TEMPLATE_BINDING_CHANGED')
    for _, request in requests:
        identity = by_model[request.metadata['model']]
        check(identity['digest'] == request.metadata['model_digest'].removeprefix('sha256:'),
              'PILOT_MODEL_DIGEST_BINDING_CHANGED')
        proof = ContextProof(**proofs[digest(request.body)])
        proof.verify(request)
        check(proof.template_sha256 == identity['template_sha256'], 'PILOT_CONTEXT_TEMPLATE_CHANGED')
    return native_metadata


def operational_summary(plan, results, attempts, *, status, execution_id, error=None):
    rows = []
    for model in MODELS:
        for mode in request_v2.MODES:
            items = [r for r in results if r['model'] == model and r['mode'] == mode]
            reasons = {}
            for item in items:
                reason = item['done_reason']
                if type(reason) is str:
                    reasons[reason] = reasons.get(reason, 0) + 1
            attempted = sum(a['model'] == model and a['mode'] == mode for a in attempts)
            rows.append(dict(model=model, mode=mode, attempted_calls=attempted,
                provider_success=sum(i['provider_kind'] == 'FINAL' for i in items),
                provider_failure=sum(i['provider_kind'] != 'FINAL' for i in items),
                parser_valid=sum((i['parser'] or {}).get('status') == 'VALID_OUTPUT' for i in items),
                parser_failure=sum((i['parser'] or {}).get('status') == 'PARSER_FAILURE' for i in items),
                unsettled_calls=attempted-len(items),
                stop_reasons=reasons, length_stops=reasons.get('length', 0)))
    return dict(format='output-interface-pilot-v2-operational-summary', status=status,
        execution_id=execution_id, planned_calls=plan['planned_calls'],
        attempted_calls=len(attempts), unsettled_calls=len(attempts)-len(results),
        provider_success=sum(r['provider_kind'] == 'FINAL' for r in results),
        error=error, rows=rows)


def run_pilot(prepared, cases, model_digests, runtime_binding, context_proofs, output, *,
              confirm_development_interface_pilot=False, root=preparer.ROOT,
              research=preparer.RESEARCH, client=None):
    """No SQL, reference evaluation, retries, resume, mode fallback or Main dispatch."""
    check(confirm_development_interface_pilot is True, 'DEVELOPMENT_INTERFACE_PILOT_CONFIRMATION_REQUIRED')
    prepared, output = Path(prepared).resolve(), Path(output).resolve()
    check(not prepared.is_relative_to(Path(research).resolve()), 'RESEARCH_REPOSITORY_READ_ONLY')
    check(not output.is_relative_to(Path(research).resolve()), 'RESEARCH_REPOSITORY_READ_ONLY')
    check(not output.is_relative_to(prepared) and not prepared.is_relative_to(output),
          'SEPARATE_NEW_EXECUTION_DIRECTORY_REQUIRED')
    check(not (prepared/'live-dispatch.json').exists(), 'PILOT_ALREADY_CLAIMED_NO_REDISPATCH')
    check(not output.exists(), 'NEW_EXECUTION_DIRECTORY_REQUIRED')
    plan, files, requests = load_prepared(prepared, cases, model_digests, root=root, research=research)
    binding_raw, proofs_raw = Path(runtime_binding).read_bytes(), Path(context_proofs).read_bytes()
    binding, proofs = loads(binding_raw), loads(proofs_raw)
    native_metadata = verify_bindings(binding, proofs, requests, root=root)
    # Verify all requested models before claiming this single-use package.
    check(freeze.verify_live(binding, Path(root)) is True, 'RUNTIME_IDENTITY_UNVERIFIED')
    client = client if client is not None else provider.OllamaClient(
        ENDPOINT, request_validator=request_v2.validate_request_v2)
    check(not isinstance(client, provider.OllamaClient) or
          (client.request_validator is request_v2.validate_request_v2 and
           client.target.geturl() == ENDPOINT), 'EXACT_LOCAL_OLLAMA_V2_BOUNDARY_REQUIRED')
    execution_id = str(uuid.uuid4())
    execution = dict(format='output-interface-pilot-v2-execution', execution_id=execution_id,
        purpose='development_output_interface_pilot', created_at=utc_now(), endpoint=ENDPOINT,
        manifest_sha256=digest(files['manifest.json']), runtime_binding_sha256=digest(binding_raw),
        context_proofs_sha256=digest(proofs_raw), pilot_runner_sha256=digest(Path(__file__).read_bytes()),
        provider_sha256=digest(Path(provider.__file__).read_bytes()), cases=list(cases),
        native_metadata_sha256={n: digest(b) for n, b in native_metadata.items()},
        planned_calls=18, repetition=1, retry_policy='NONE_STOP_ON_PROVIDER_FAILURE')
    output.mkdir(parents=True, exist_ok=False)
    # The same preparation cannot be dispatched again, even to another output.
    # Concurrent processes must claim this exclusive marker before any send.
    publish(prepared/'live-dispatch.json', encode({**execution, 'output': str(output)}))
    publish(output/'execution.json', encode(execution))
    publish(output/'runtime-binding.json', binding_raw)
    publish(output/'context-proofs.json', proofs_raw)
    for name, raw in native_metadata.items():
        target = output/'native-metadata'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        publish(target, raw)
    for name, raw in files.items():
        target = output/'prepared'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        publish(target, raw)
    results, status, error = [], 'COMPLETED', None
    current = None
    try:
        for slot, request in requests:
            current = slot['slot']
            # Drift after earlier calls stops the pilot before the next attempt.
            check(all((Path(root)/runtime_evidence.DIRECTORY/n).read_bytes() == b
                      for n, b in native_metadata.items()), 'NATIVE_METADATA_SNAPSHOT_CHANGED')
            check(freeze.verify_live(binding, Path(root)) is True, 'RUNTIME_IDENTITY_UNVERIFIED')
            check(parser.artifact_hash() == plan['parser_sha256'], 'PARSER_ARTIFACT_CHANGED')
            request_v2.validate_request_v2(request)
            directory = output/f"calls/{current:02}"
            directory.mkdir(parents=True, exist_ok=False)
            reservation = dict(**slot, execution_id=execution_id, attempt=1,
                pilot_version=plan['format'], request_provenance=request.metadata,
                generation_settings=loads(request.body)['options'], runtime_verified_at=utc_now())
            publish(directory/'reservation.json', encode(reservation))

            def on_start(started_at):
                publish(directory/'started.json', encode(dict(started_at=started_at,
                    execution_id=execution_id, request_sha256=digest(request.body))))

            receipt = client.send(request, on_start=on_start)
            check(type(receipt) is provider.Receipt, 'PROVIDER_RECEIPT_REQUIRED')
            # Preserve the envelope/partial bytes durably BEFORE classification/parsing.
            if receipt.raw is not None:
                publish(directory/'response.bin', receipt.raw)
            publish(directory/'receipt.json', encode(dict(transport=receipt.transport,
                started_at=receipt.started_at, received_at=receipt.received_at,
                raw_response_sha256=None if receipt.raw is None else digest(receipt.raw))))
            result = provider.classify(receipt)
            # Even an unusable envelope may contain final/thinking text worth retaining.
            metadata = result.metadata if isinstance(result.metadata, dict) else {}
            message = metadata.get('message')
            for field in ('content', 'thinking'):
                text = message.get(field) if isinstance(message, dict) else None
                if type(text) is str:
                    publish(directory/(field+'.txt'), text.encode('utf-8', errors='surrogatepass'))
            parsed = parser.parse(result.content) if result.kind == 'FINAL' else None
            record = dict(**reservation, started_at=receipt.started_at, received_at=receipt.received_at,
                raw_response_sha256=None if receipt.raw is None else digest(receipt.raw),
                raw_response_path=None if receipt.raw is None else f'calls/{current:02}/response.bin',
                provider_kind=result.kind, provider_code=result.code,
                done_reason=metadata.get('done_reason'),
                parser=None if parsed is None else asdict(parsed))
            publish(directory/'result.json', encode(record))
            results.append(record)
            if result.kind != 'FINAL':
                status, error = 'STOPPED_PROVIDER_FAILURE', result.code
                break
    except (Exception, KeyboardInterrupt) as exc:
        status, error = 'STOPPED_REQUIRES_MANUAL_REVIEW', f'{type(exc).__name__}: {exc}'
        publish(output/'stop.json', encode(dict(execution_id=execution_id, slot=current,
            error=error, stopped_at=utc_now(), instruction='Inspect durable call evidence; never redispatch this package')))
    # A started but unsettled call is observable, but cannot be called success/failure.
    attempts = [loads(p.with_name('reservation.json').read_bytes())
                for p in sorted((output/'calls').glob('*/started.json'))]
    summary = operational_summary(plan, results, attempts, status=status,
                                  execution_id=execution_id, error=error)
    publish(output/'summary.json', encode(summary))
    return summary


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('action', choices=['run'])
    cli.add_argument('--prepared', type=Path, required=True)
    cli.add_argument('--cases', nargs=2, choices=preparer.DEV_CASES, required=True)
    cli.add_argument('--model-digests', type=Path, required=True)
    cli.add_argument('--runtime-binding', type=Path, required=True)
    cli.add_argument('--context-proofs', type=Path, required=True)
    cli.add_argument('--output', type=Path, required=True)
    cli.add_argument('--confirm-development-interface-pilot', action='store_true', required=True)
    args = cli.parse_args(argv)
    try:
        summary = run_pilot(args.prepared, args.cases, loads(args.model_digests.read_bytes()),
            args.runtime_binding, args.context_proofs, args.output,
            confirm_development_interface_pilot=args.confirm_development_interface_pilot)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        cli.exit(1, f'Pilot blocked or stopped: {exc}\nInspect any execution evidence; no redispatch is performed.\n')
    print(f"{summary['status']}: {summary['attempted_calls']}/18 attempted calls; {args.output/'summary.json'}")
    return 0 if summary['status'] == 'COMPLETED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
