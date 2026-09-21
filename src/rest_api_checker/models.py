"""Scientific labels are separate from diagnostics and incomplete execution."""
from dataclasses import dataclass
from enum import StrEnum


class State(StrEnum):
    PASS = 'PASS'
    FAIL = 'FAIL'
    NOT_APPLICABLE = 'NOT_APPLICABLE'


class Overall(StrEnum):
    CONSISTENT = 'CONSISTENT'
    INCONSISTENT = 'INCONSISTENT'


@dataclass(frozen=True, order=True)
class Diagnostic:
    code: str
    instance_pointer: str = ''
    schema_path: str = ''
    keyword: str = ''


@dataclass(frozen=True)
class OracleResult:
    c1: State
    c2: State
    c3: State
    selected_response: str | None
    selected_media: str | None
    schema_pointer: str | None
    diagnostics: tuple[Diagnostic, ...]

    @property
    def overall(self) -> Overall:
        return Overall.INCONSISTENT if State.FAIL in self.vector else Overall.CONSISTENT

    @property
    def vector(self) -> tuple[State, State, State]:
        return self.c1, self.c2, self.c3


class OracleNotReady(Exception):
    """Out-of-profile or unusable evidence. No completed labels are produced."""

    def __init__(self, code: str, detail: str = ''):
        self.code = code
        self.detail = detail
        super().__init__(f'{code}: {detail}' if detail else code)


class OracleExecutionError(Exception):
    """Validator/infrastructure failure; never a scientific FAIL or N/A."""
