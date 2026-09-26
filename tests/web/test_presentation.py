"""Fabricated immutable report projections, without provider or study execution."""
from copy import deepcopy
from pathlib import Path

import pytest
from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader, select_autoescape

from rest_api_checker.web.presentation import (
    BLUE, CHARCOAL, GREEN, evaluation_view, format_ratio, model_name,
)


MODELS = ("qwen3.6:27b", "gemma3:27b", "mistral-small3.2:24b")
CATEGORIES = ("c1", "c2", "c3")


def ratio(numerator, denominator):
    return {"numerator": numerator, "denominator": denominator,
            "value": f"{numerator}/{denominator}" if denominator else None}


@pytest.fixture
def report():
    metrics, diagnostics = {}, {}
    for index, prompt in enumerate(("P1", "P2", "P3")):
        metrics[prompt] = {
            "Score": ratio(310 + index, 324), "Robust": ratio(30 + index, 36),
            "StableCorrect": ratio(90 + index, 108), "Reliability": ratio(105 + index, 108),
            "FullCase": ratio(99 + index, 108), "Length": 100 + index, "Order": index,
            "cells": {model: {category: ratio(30 + model_index + index, 36)
                                for category in CATEGORIES}
                      for model_index, model in enumerate(MODELS)},
        }
        diagnostics[prompt] = {
            model: {"reliability": ratio(34, 36), "full_case": ratio(31, 36),
                    "stable_correct": {category: ratio(10, 12) for category in CATEGORIES},
                    "outcomes": {"valid": 34, "parser_failure": 1, "technical_failure": 1},
                    "valid_coverage": ratio(34, 36), "valid_triple_coverage": ratio(10, 12),
                    "repeat_disagreement": {key: ratio(1, 10) for key in (*CATEGORIES, "vector")},
                    "valid_only": {category: ratio(30, 34) for category in CATEGORIES},
                    "per_repetition": {"1": {category: ratio(10, 12) for category in CATEGORIES}},
                    "confusion": {category: {reference: {prediction: 0 for prediction in
                        ("PASS", "FAIL", "NOT_APPLICABLE")} for reference in
                        ("PASS", "FAIL", "NOT_APPLICABLE")} for category in CATEGORIES}}
            for model in MODELS
        }
    return {"format": "comparison-evaluation-v1", "fabricated": True,
            "metrics": metrics, "diagnostics": diagnostics,
            "selected_prompt": "P2", "ranking": ["P2", "P3", "P1"],
            "tie_break_trace": [{"criterion": "Score", "values": {"P2": "78/81"},
                                 "remaining": ["P2"]}]}


def test_uses_recorded_selection_and_ranking_without_reranking(report):
    before = deepcopy(report)
    value = evaluation_view(report)
    assert value["prompt"] == value["selected_prompt"] == "P2"
    assert value["ranking"] == ["P2", "P3", "P1"]
    assert value["metrics"] is report["metrics"]["P2"]
    assert value["trace"] is report["tie_break_trace"]
    assert report == before


def test_no_selection_is_inferred_from_metrics_or_ranking(report):
    report.pop("selected_prompt")
    value = evaluation_view(report)
    assert value["prompt"] == "P1"
    assert value["selected_prompt"] is None
    assert evaluation_view(report, prompt="P3")["prompt"] == "P3"


def test_model_chart_preserves_cell_values_and_named_colors(report):
    value = evaluation_view(report, prompt="P1")
    chart = value["chart"]
    assert chart["type"] == "bar"
    assert chart["data"]["labels"] == ["C1", "C2", "C3"]
    assert [d["label"] for d in chart["data"]["datasets"]] == ["Qwen", "Gemma", "Mistral"]
    assert [d["backgroundColor"] for d in chart["data"]["datasets"]] == [BLUE, GREEN, CHARCOAL]
    assert chart["data"]["datasets"][0]["data"] == pytest.approx([83.333333] * 3)
    assert chart["data"]["datasets"][0]["counts"] == ["83.3% (30 / 36)"] * 3


def test_prompt_chart_uses_all_stored_cells_without_new_aggregate(report):
    value = evaluation_view(report, view="prompts")
    datasets = value["chart"]["data"]["datasets"]
    assert len(value["chart"]["data"]["labels"]) == 9
    assert [d["label"] for d in datasets] == ["P1", "P2", "P3"]
    assert len(datasets[0]["data"]) == 9
    assert datasets[0]["counts"][0] == "83.3% (30 / 36)"
    robust = evaluation_view(report, view="prompts", metric="Robust")
    assert robust["chart"]["data"]["labels"] == ["Robust"]
    assert robust["chart"]["data"]["datasets"][0]["counts"] == ["83.3% (30 / 36)"]


@pytest.mark.parametrize("view,metric", [("models", "Robust"), ("categories", "Reliability"),
                                         ("categories", "FullCase"), ("models", "invented")])
def test_unsupported_metric_dimension_is_not_calculated(report, view, metric):
    value = evaluation_view(report, view=view, metric=metric)
    assert value["chart_metric"] == "Correctness"
    assert metric not in value["chart_metrics"]


def test_category_and_model_diagnostic_charts_use_existing_diagnostics(report):
    stable = evaluation_view(report, view="categories", metric="StableCorrect")
    assert stable["chart"]["data"]["labels"] == ["Qwen", "Gemma", "Mistral"]
    assert stable["chart"]["data"]["datasets"][0]["counts"] == ["83.3% (10 / 12)"] * 3
    reliability = evaluation_view(report, view="models", metric="Reliability")
    assert reliability["chart"]["data"]["datasets"][0]["counts"] == ["94.4% (34 / 36)"]


def test_missing_undefined_and_zero_are_distinct(report):
    assert format_ratio(None) == "Not available"
    assert format_ratio({}) == "Not available"
    assert format_ratio(ratio(0, 0)) == "N/A (0 / 0)"
    assert format_ratio(ratio(0, 36)) == "0.0% (0 / 36)"
    report["diagnostics"]["P2"][MODELS[0]]["reliability"] = ratio(0, 0)
    chart = evaluation_view(report, metric="Reliability")["chart"]
    assert chart["data"]["datasets"][0]["data"] == [None]


def test_unknown_model_identity_is_retained_and_unsupported_report_rejected(report):
    assert model_name("qwen3.6:27b") == "Qwen"
    assert model_name("future-exact-model:1") == "future-exact-model:1"
    report["format"] = "future-main-evaluation"
    with pytest.raises(ValueError, match="not supported"):
        evaluation_view(report)


def render_template(**context):
    """Render the owned template without depending on concurrent shell changes."""
    template_dir = Path(__file__).parents[2] / "src/rest_api_checker/web/templates"
    shell = {
        "base.html": "{% block content %}{% endblock %}{% block scripts %}{% endblock %}",
        "macros.html": "{% macro metric(label, value) %}<div>{{ label }} {{ value|ratio }}</div>{% endmacro %}"
                       "{% macro experiment_selector(experiments, selected_experiment) %}{% endmacro %}"
                       "{% macro technical(mapping) %}{{ mapping }}{% endmacro %}",
    }
    env = Environment(loader=ChoiceLoader([DictLoader(shell), FileSystemLoader(template_dir)]),
                      autoescape=select_autoescape())
    env.filters["ratio"] = format_ratio
    return env.get_template("evaluation.html").render(
        experiments=[], selected_experiment=1, query_url=lambda **kw: "/evaluation",
        url_for=lambda name, **kw: "/static/" + kw.get("path", "").lstrip("/"), **context)


def test_incomplete_template_has_operational_counts_and_no_scientific_metrics():
    html = render_template(evaluation=None, report=None,
        experiment={"completed": 217, "planned": 324, "parser_failure": 2, "technical_failure": 1},
        evaluation_unavailable_reason="Evaluation becomes available after experiment completion.")
    assert "217 / 324" in html and "67.0%" in html
    assert "Parser failures" in html and "Technical failures" in html
    assert "Category correctness" not in html and 'id="chart-data"' not in html
    assert ">P1<" in html and ">P2<" in html and ">P3<" in html


def test_template_safe_escaping_and_chart_json_cannot_close_script(report):
    hostile = '</script><script>alert("persisted")</script>'
    for prompt in report["metrics"]:
        report["metrics"][prompt]["cells"][hostile] = report["metrics"][prompt]["cells"].pop(MODELS[0])
        report["diagnostics"][prompt][hostile] = report["diagnostics"][prompt].pop(MODELS[0])
    view = evaluation_view(report)
    html = render_template(evaluation=view, report=report, experiment={})
    assert hostile not in html
    assert "&lt;/script&gt;&lt;script&gt;" in html
    assert "\\u003c/script\\u003e" in html
    assert "FABRICATED / TEST DATA" in html
    assert "Detailed diagnostics" in html and "NOT_APPLICABLE" in html
