"""Minimal OpenAPI-based reference oracle."""
from .models import Diagnostic, OracleExecutionError, OracleNotReady, OracleResult, Overall, State
from .oracle import evaluate_response

__all__ = ['evaluate_response', 'Diagnostic', 'OracleExecutionError', 'OracleNotReady', 'OracleResult', 'Overall', 'State']
