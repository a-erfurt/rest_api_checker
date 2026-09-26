"""SQL Server persistence only; no renderer, parser, provider or evaluation engine."""

from .database import connect
from .repository import Repository

__all__ = ['Repository', 'connect']
