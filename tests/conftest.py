"""Verify byte identity before any test can use the frozen contract copies."""
import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / 'tests/contracts/provenance.json').read_text())


def verified_bytes():
    result = {}
    for api, record in MANIFEST['contracts'].items():
        raw = (ROOT / record['copy']).read_bytes()
        actual = hashlib.sha256(raw).hexdigest()
        if actual != record['sha256']:
            raise pytest.UsageError(f'{api} contract hash mismatch: {actual}')
        result[api] = raw
    return result


def pytest_sessionstart(session):
    verified_bytes()


def pytest_sessionfinish(session, exitstatus):
    verified_bytes()


@pytest.fixture
def contracts():
    # Fresh independent documents per test; no reads/writes to the research repo.
    return {api: json.loads(raw) for api, raw in verified_bytes().items()}


@pytest.fixture
def contract_paths():
    verified_bytes()
    return {api: ROOT / record['copy'] for api, record in MANIFEST['contracts'].items()}


@pytest.fixture
def operations():
    return {api: record['operation_path'] for api, record in MANIFEST['contracts'].items()}
