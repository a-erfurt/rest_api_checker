"""Run the presentation notebook in one fresh, isolated local Jupyter kernel.

Only execution outputs/metadata are saved; cells are authored via the notebook
editing tools. No product modules, evaluator entry point or external services.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

import nbformat
from jupyter_client import KernelManager
from jupyter_client.kernelspec import KernelSpecManager
from nbclient import NotebookClient

BASE = Path(__file__).resolve().parents[1]
EXPECTED_PYTHON = BASE / ".venv/bin/python"
if Path(sys.prefix).resolve() != (BASE / ".venv").resolve():
    raise RuntimeError("Run with the isolated analysis interpreter.")
for name, subdir in [("MPLCONFIGDIR", "matplotlib"), ("IPYTHONDIR", "ipython"),
                     ("JUPYTER_RUNTIME_DIR", "runtime"), ("JUPYTER_CONFIG_DIR", "config"),
                     ("JUPYTER_DATA_DIR", "data")]:
    folder = BASE / ".jupyter" / subdir
    folder.mkdir(parents=True, exist_ok=True)
    os.environ[name] = str(folder)
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
kernel_dir = BASE / ".jupyter/kernels/evaluation-v2-analysis"
kernel_dir.mkdir(parents=True, exist_ok=True)
spec = {"argv": [str(EXPECTED_PYTHON), "-m", "ipykernel_launcher", "-f", "{connection_file}"],
        "display_name": "Evaluation v2 analysis (Python 3.12)", "language": "python"}
(kernel_dir / "kernel.json").write_text(json.dumps(spec, indent=2) + "\n")
path = BASE / "evaluation_v2_figures.ipynb"
notebook = nbformat.read(path, as_version=4)
for cell in notebook.cells:
    cell.metadata.pop("ExecuteTime", None)
manager = KernelManager(kernel_name="evaluation-v2-analysis",
                        kernel_spec_manager=KernelSpecManager(kernel_dirs=[str(kernel_dir.parent)]))
client = NotebookClient(notebook, km=manager, timeout=120,
                        resources={"metadata": {"path": str(BASE)}},
                        store_widget_state=False, allow_errors=False)
client.owns_km = True
print("Starting fresh analysis kernel:", EXPECTED_PYTHON, flush=True)
started = time.monotonic()
try:
    client.execute()
except Exception:
    # Preserve actual outputs and error evidence; never pretend a failed run passed.
    nbformat.write(notebook, path)
    raise
nbformat.write(notebook, path)
code_cells = [c for c in notebook.cells if c.cell_type == "code"]
if any(c.execution_count is None for c in code_cells):
    raise RuntimeError("An execution count is missing.")
receipt_path = BASE / "provenance/execution_log.json"
records = json.loads(receipt_path.read_text()) if receipt_path.exists() else []
records.append({"status": "PASS", "fresh_kernel": True, "interpreter": str(EXPECTED_PYTHON),
                "code_cells": len(code_cells), "execution_counts": [c.execution_count for c in code_cells],
                "elapsed_seconds": round(time.monotonic() - started, 3),
                "notebook_sha256_after_save": hashlib.sha256(path.read_bytes()).hexdigest(),
                "method": "nbclient; notebook source code executes inside the isolated kernel",
                "fingerprint": json.loads((BASE / "provenance/reproduction.json").read_text())["fingerprint"]})
receipt_path.write_text(json.dumps(records, indent=2, sort_keys=True) + "\n")
manifest_path = BASE / "provenance/manifest.json"
manifest = json.loads(manifest_path.read_text())
manifest["notebook_file_hash"] = {"path": path.name,
                                  "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                  "scope": "Saved notebook including execution outputs."}
manifest["execution_script_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
print("PASS:", len(code_cells), "code cells; fresh kernel stopped.", flush=True)
