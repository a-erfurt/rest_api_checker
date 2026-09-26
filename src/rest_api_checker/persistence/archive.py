"""Portable byte export from an explicit hash-bound file closure."""
from hashlib import sha256
import os
from pathlib import Path

from .database import json_bytes, require


def export_files(repo, closure, directory):
    """New directory only. Hash-addressed bytes plus original path/role mapping.

    Export failure leaves visible partial evidence, never a complete manifest.
    No lossy decoding, path traversal, overwrite or automatic cleanup.
    """
    repo.verify_closure(closure)
    target = Path(directory)
    target.mkdir(mode=0o700,parents=True,exist_ok=False)
    exported = set()
    for item in closure:
        raw = repo.file(item['file_id'])
        digest = sha256(raw).hexdigest()
        if digest not in exported:
            with (target/(digest+'.bin')).open('xb') as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            exported.add(digest)
    with (target/'manifest.json').open('xb') as stream:
        stream.write(json_bytes(dict(format='rest-api-checker-file-export-v1',files=closure)))
        stream.flush()
        os.fsync(stream.fileno())
    descriptor = os.open(target,os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    require(all(sha256((target/(digest+'.bin')).read_bytes()).hexdigest()==digest for digest in exported), 'Export mismatch')
    return target/'manifest.json'
