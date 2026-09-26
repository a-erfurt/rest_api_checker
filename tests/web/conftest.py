"""In-process web clients over explicitly fabricated read projections."""
import pytest
from fastapi.testclient import TestClient

from .browser_fixture import FabricatedQueries, query_factory
from rest_api_checker.web.app import create_app


@pytest.fixture
def queries():
    return FabricatedQueries()


@pytest.fixture
def client(queries):
    with TestClient(create_app(query_factory=query_factory(queries))) as client:
        yield client


@pytest.fixture(autouse=True)
def forbid_execution_from_web(monkeypatch):
    """Page requests must never invoke execution, evaluation creation or repair."""
    from rest_api_checker import evaluation, preflight
    from rest_api_checker.experiment import batch, orchestration
    def forbidden(*args, **kwargs):
        pytest.fail('The web UI must not execute, reconstruct or evaluate study data')
    for module, names in (
        (evaluation, ('evaluate','create_report','analysis_input')),
        (preflight, ('check',)),
        (batch, ('run',)),
        (orchestration, ('prepare',)),
    ):
        for name in names:
            monkeypatch.setattr(module,name,forbidden)
