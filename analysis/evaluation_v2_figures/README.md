# Evaluation v2 figures: Experiment 10003

This folder presents the unchanged, completed evaluation. Its two read-only ZIP
copies in `provenance/inputs/` are hash-bound inputs. The notebook reads them in
memory. It never invokes the evaluator's `analyze()` function, the product, a
model server, a studied API or a database. Existing evaluator definitions are
used only to check the archived tables against the archived CSV.

## Interpreter and PyCharm

Use the isolated Python 3.12 interpreter at
`analysis/evaluation_v2_figures/.venv/bin/python`. Select that interpreter/kernel
for this notebook **before** running cells. Do not accept installation into the
product interpreter: PyCharm can otherwise add `ipykernel` to the product's
`pyproject.toml` and `uv.lock` automatically. A preliminary kernel start exposed
this behavior; that dependency change was reversed and the added packages removed.

This interpreter is installed and verified with Python 3.12.14, pandas 2.2.3 and
Matplotlib 3.10.9. `requirements-analysis-frozen.txt` records all 49 installed
package versions. To recreate it, installation is limited to this folder:

```bash
UV_CACHE_DIR=analysis/evaluation_v2_figures/.uv-cache /opt/homebrew/bin/uv venv --python /Users/aerfurt/University/Bachelor/rest_api_checker/.venv/bin/python analysis/evaluation_v2_figures/.venv
UV_CACHE_DIR=analysis/evaluation_v2_figures/.uv-cache /opt/homebrew/bin/uv pip install --python analysis/evaluation_v2_figures/.venv/bin/python -r analysis/evaluation_v2_figures/requirements-analysis-frozen.txt
```

Open `evaluation_v2_figures.ipynb`, set the working directory to this folder or
the repository root, restart the selected kernel, then run all cells in order.
The notebook requires no input and performs no downloads. Restart the kernel
and run all cells again to compare exports in the same environment. A source or
environment change starts a new reproduction fingerprint. Only repeated passes
for an identical fingerprint establish byte equality.

The delivered execution was headless, using fresh isolated Jupyter kernels, not
a PyCharm desktop UI test. The local reproduction command is:

```bash
PYTHONDONTWRITEBYTECODE=1 analysis/evaluation_v2_figures/.venv/bin/python analysis/evaluation_v2_figures/provenance/execute_notebook.py
```

Run that command twice from the repository root. The runner saves the actual
cell outputs, stops each kernel, records execution receipts, and finalizes the
saved notebook hash. It does not install packages or change the product SDK.

## Outputs and definitions

`figures/` contains the three current figures in German (`_de`) and English
(`_en`), each as vector PDF and 300 dpi PNG. The six unsuffixed files are
unchanged historical exports; use the suffixed versions for the thesis.
`provenance/figure_data/` contains the actual drawing data. The figure width is
398.33864 TeX-pt, read from the existing thesis log, and centrally configurable.

- RQ1 uses correct / planned vectors; conditional accuracy and validity coverage
  remain visible in the accompanying table. There are zero technical failures.
- RQ2 plots correct / planned reference-applicable category checks. T-DIM also
  preserves full state agreement and both directions of applicability errors.
- RQ3 counts 82 case-model triples per model. Incomplete triples stay incomplete;
  three identical valid NNN vectors are stable wrong. The conditional identity
  rate uses complete valid triples only.

`tables/` provides T-DAT, T-SET, T-BIN, T-DIM, T-GRP and T-PAIR as CSV and LaTeX,
plus the full existing RQ1/RQ3 summaries and repetition tables. LaTeX assigns
numbers through the stable `tab_v2_*` labels. The files require `booktabs`; the
appendix and setup tables additionally require `longtable`. Appendix rates are
displayed to four decimal places and counts as integers; CSV files retain the
source values.

The reference-group and API blocks in T-GRP describe the same dataset and must
not be added. Pair comparisons use only the existing 39 links in Main. A missing
binary prediction is excluded from TP/TN/FP/FN and remains visible in coverage.

## Verification evidence

`provenance/checks.json` records source binding and count controls.
`provenance/reproduction.json` compares output hashes across complete runs with
fresh kernels. `provenance/manifest.json` binds versions, source and output hashes;
it deliberately does not hash itself. Execution and visual-review evidence is
recorded separately. No PyCharm desktop UI inspection is inferred from a headless
execution or from notebook tool output.

No thesis chapters, existing thesis figures or scientific inputs are edited.
The original package delivery did not include a commit or push.

## Unified column design

All six current language variants use a 398.33864 TeX-pt wide by 3.8 inch
canvas, fixed identical axes bounds, white backgrounds, light horizontal grids,
and a horizontal legend above the plot. All bars have solid RUB colors without
hatches or outlines. Titles remain the responsibility of the LaTeX captions.
RQ1 and RQ3 use stacked columns with count labels and short external leaders for
small segments. RQ2 uses grouped columns; its horizontal numerator/denominator
labels are staggered to prevent overlap. RQ2's extra space above 100% is reserved
for these labels; the bar values are unchanged.

`provenance/unified_design_verification.json` records the current visual review,
two successful fresh-kernel executions, identical DE/EN geometry, and byte-exact
preservation of all 32 table/drawing exports and the numerical control report.
`provenance/unified_design_source.diff` records the presentation-only source
changes against the pre-redesign notebook. Earlier palette and bilingual review
receipts describe their historical versions. The current notebook additionally
checks bar styling and text collisions before each language export.
