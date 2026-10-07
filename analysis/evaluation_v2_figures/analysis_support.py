"""Presentation-only helpers; no result definitions or scientific evaluation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2,
                                    sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def tex_escape(value):
    replacements = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%",
                    "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{",
                    "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
    return "".join(replacements.get(char, char) for char in str(value))


def export_table(base, name, frame, caption, view=None, note="", columns=None,
                 block_column=None, long=False):
    """Keep a machine-readable CSV and export the displayed compact LaTeX view."""
    folder = Path(base) / "tables"
    frame.to_csv(folder / (name + ".csv"), index=False, lineterminator="\n")
    view = frame if view is None else view
    column_spec = columns or ("l" + "r" * (len(view.columns) - 1))
    header = " & ".join(tex_escape(c) for c in view.columns) + r" \\"
    lines = ["% Generated from hash-bound Experiment 10003 results.",
             "% Requires booktabs" + (" and longtable." if long else ".")]
    if long:
        lines += [r"\begingroup\small", r"\begin{longtable}{" + column_spec + "}",
                  r"\caption{" + tex_escape(caption) + r"}\label{" + name + r"}\\",
                  r"\toprule", header, r"\midrule", r"\endfirsthead",
                  r"\toprule", header, r"\midrule", r"\endhead"]
    else:
        lines += [r"\begin{table}[htbp]", r"\centering\small",
                  r"\caption{" + tex_escape(caption) + "}", r"\label{" + name + "}",
                  r"\begin{tabular}{" + column_spec + "}", r"\toprule", header, r"\midrule"]
    previous = None
    for _, row in view.iterrows():
        if block_column is not None and previous is not None and row[block_column] != previous:
            lines.append(r"\midrule")
        if block_column is not None:
            previous = row[block_column]
        lines.append(" & ".join(tex_escape(v) for v in row) + r" \\")
    lines += [r"\bottomrule", r"\end{longtable}" if long else r"\end{tabular}"]
    if note:
        lines += [r"\par\smallskip\noindent", r"\begin{minipage}{\linewidth}\footnotesize "
                  + tex_escape(note) + r"\end{minipage}"]
    lines += [r"\endgroup" if long else r"\end{table}"]
    (folder / (name + ".tex")).write_text("\n".join(lines) + "\n", encoding="utf-8")


def save_figure(base, name, figure, data):
    """Export actual drawing data plus vector PDF and PNG with fixed metadata."""
    base = Path(base)
    data.to_csv(base / "provenance/figure_data" / (name + ".csv"),
                index=False, lineterminator="\n")
    figure.savefig(base / "figures" / (name + ".pdf"),
                   metadata={"CreationDate": None, "ModDate": None,
                             "Creator": "Evaluation v2 presentation notebook"})
    figure.savefig(base / "figures" / (name + ".png"), dpi=300,
                   metadata={"Software": "Evaluation v2 presentation notebook"})


def artifact_hashes(base):
    base = Path(base)
    files = list((base / "figures").glob("*")) + list((base / "tables").glob("*"))
    files += list((base / "provenance/figure_data").glob("*.csv"))
    return {str(path.relative_to(base)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(files) if path.is_file()}
