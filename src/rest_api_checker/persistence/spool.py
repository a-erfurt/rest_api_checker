"""Append-only, atomic local recovery evidence. Never calls a provider or parses output."""
import base64
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile

from .database import json_bytes, require, timestamp


def stage(directory, *, run_id, attempt_id, request_sha256, setup_sha256, response, transport,
          received_at=None, started_at=None):
    """Fsync complete envelope then publish without overwrite via atomic hard link.

    NULL response is absent; base64('') is explicitly captured empty bytes.
    A failed fsync/publish raises. Caller must pause, never infer retry entitlement.
    The receipt-to-fsync crash window cannot be eliminated by this helper.
    """
    require(type(run_id) is int and run_id>0 and type(attempt_id) is int and attempt_id>0, 'Invalid spool identities')
    require(response is None or type(response) is bytes, 'Exact response bytes required')
    for value in (request_sha256,setup_sha256):
        require(len(value)==64 and all(c in '0123456789abcdef' for c in value), 'Invalid identity hash')
    require(isinstance(transport,dict), 'Explicit transport evidence required')
    value = dict(format='rest-api-checker-recovery-v1',run_id=run_id,attempt_id=attempt_id,
        request_sha256=request_sha256,setup_sha256=setup_sha256,
        response_base64=None if response is None else base64.b64encode(response).decode('ascii'),
        response_sha256=None if response is None else sha256(response).hexdigest(),transport=transport,
        received_at=timestamp(received_at),started_at=timestamp(started_at))
    content = json_bytes(value)
    digest = sha256(content).hexdigest()
    envelope = json_bytes(dict(sha256=digest,payload=value))
    root = Path(directory)
    root.mkdir(mode=0o700,parents=True,exist_ok=True)
    destination = root/f'{run_id}-{attempt_id}-{digest}.json'
    descriptor, temporary = tempfile.mkstemp(prefix='.incomplete-',dir=root)
    try:
        with os.fdopen(descriptor,'wb') as stream:
            stream.write(envelope)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary,destination)  # Atomic no-clobber publication on the same filesystem.
        except FileExistsError:
            require(destination.read_bytes()==envelope, 'Spool name/content conflict')
        dir_fd = os.open(root,os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        # A failed write retains any available temporary bytes for manual recovery.
        if destination.exists() and Path(temporary).read_bytes()==envelope:
            Path(temporary).unlink()
    return destination


def read(path):
    raw = Path(path).read_bytes()
    envelope = json.loads(raw)
    value = envelope['payload']
    require(sha256(json_bytes(value)).hexdigest()==envelope['sha256'], 'Spool checksum mismatch')
    require(value['format']=='rest-api-checker-recovery-v1', 'Unknown spool format')
    response = None if value['response_base64'] is None else base64.b64decode(value['response_base64'],validate=True)
    require((None if response is None else sha256(response).hexdigest())==value['response_sha256'], 'Spool response checksum mismatch')
    return raw,value,response


def reconcile(repo, path, *, outcome=None):
    """Import evidence, optionally replay an already adjudicated finalization.

    outcome contains the explicit future parser/transport result; no inferred
    outcome, new reservation or dispatch. Conflicts leave the spool untouched.
    Without an outcome, retain response/transport as a diagnostic successor and
    leave the attempt/run pending. Later finalization must retain that chain.
    """
    raw,value,response = read(path)
    with repo.transaction():
        from .database import lock
        lock(repo.cn,f'run:{value["run_id"]}')
        attempt = repo._row('run_attempts',value['attempt_id'])
        require(attempt['run_id']==value['run_id'], 'Spool attempt/run mismatch')
        require(sha256(repo.file(attempt['request_file_id'])).hexdigest()==value['request_sha256'], 'Spool request mismatch')
        run = repo._row('experiment_runs',attempt['run_id'])
        experiment = repo._row('experiments',run['experiment_id'])
        require(sha256(repo.file(experiment['setup_file_id'])).hexdigest()==value['setup_sha256'], 'Spool setup mismatch')
        spool_id = repo.archive('recovery-spool.json',raw)
        response_id = None if response is None else repo.archive('recovery-response.bin',response)
        if outcome is not None:
            require(outcome['diagnostics'].get('spool_sha256')==sha256(raw).hexdigest(), 'Finalization must bind recovery evidence')
            return repo.finalize(value['attempt_id'],response=response,**outcome)
        # Repeated evidence-only reconciliation is idempotent even across later successors.
        cursor = attempt['diagnostics_file_id']
        while cursor is not None:
            item = json.loads(repo.file(cursor))
            if item.get('format')!='diagnostic-successor-v1':
                break
            if item['evidence'].get('spool_sha256')==sha256(raw).hexdigest():
                return False
            cursor = item['previous_file_id']
        files = [dict(file_id=spool_id,sha256=sha256(raw).hexdigest())]
        if response_id is not None:
            files.append(dict(file_id=response_id,sha256=value['response_sha256']))
        repo.append_diagnostics(value['attempt_id'],expected_file_id=attempt['diagnostics_file_id'],
                                evidence=dict(spool_sha256=sha256(raw).hexdigest(),files=files))
        return True
