"""Manual prompt selection with fabricated catalogs; no SQL, runtime or model calls."""
from copy import deepcopy

import pytest

from rest_api_checker import live_adhoc_runtime, live_demo_cli
from test_live_demo_cli import args, console, core, no_input


@pytest.fixture(autouse=True)
def offline_runtime(monkeypatch):
    monkeypatch.setattr(live_adhoc_runtime, 'model_availability', lambda: {})
    monkeypatch.setattr(live_adhoc_runtime, 'probe_runtime', lambda: dict(
        available=True, version='test', thesis_version='test', notice=''))


@pytest.fixture
def variants(core):
    # Database IDs deliberately differ from the version numbers and menu positions.
    core.data['prompts'] = [dict(id=38, name='P3'), dict(id=12, name='P1'), dict(id=25, name='P2')]
    return core


def manual(core, answers, *flags):
    parsed = args(*flags)
    parsed.adhoc = True
    view, output = console()
    view.width = 140
    responses = iter(answers)
    value, code = live_demo_cli.run(object(), parsed, view,
        input_fn=lambda _: next(responses), interactive=True)
    assert list(responses) == [], 'Some answers were not consumed by the expected wizard flow'
    return value, code, output.getvalue()


@pytest.mark.parametrize('choice,name,prompt_id', [
    ('', 'P1', 12), ('1', 'P1', 12), ('2', 'P2', 25), ('3', 'P3', 38),
])
def test_prompt_selection_reaches_plan_and_confirmation(variants, choice, name, prompt_id):
    before = deepcopy(variants.data)
    value, code, text = manual(variants, ['1', '1', '1', choice, '1', '1', '', 'yes'])
    assert code == 0 and value['status'] == 'COMPLETED'
    assert [call for call, _ in variants.calls] == ['plan', 'execute']
    planning = variants.calls[0][1]
    assert planning['prompt_id'] == prompt_id
    assert planning['case_id'] == 11 and planning['model_ids'] == [4]
    assert planning['repetitions'] == 1 and planning['adhoc'] is True
    confirmation = text.split('Ready to run', 1)[1]
    assert next(line for line in confirmation.splitlines() if 'Prompt' in line).split()[-2] == name
    assert variants.data == before


def test_prompt_menu_is_immediately_before_case_with_clear_actual_options(variants):
    _, _, text = manual(variants, ['1', '1', '1', '', '1', '1', '', 'n'])
    headings = ['Select service', 'Select operation', 'Choose case type',
                'Select prompt', 'Select case', 'Select model', 'Ready to run']
    positions = [text.index(heading) for heading in headings]
    assert positions == sorted(positions)
    prompt_menu = text.split('Select prompt', 1)[1].split('Select case', 1)[0]
    assert prompt_menu.index('P1') < prompt_menu.index('P2') < prompt_menu.index('P3')
    for label in ('P2 — Structured C1 → C2 → C3 checklist',
                  'P1 — Minimal / direct', 'P3 — Explicit contract interpretation'):
        assert label in prompt_menu
    assert 'q Back' in prompt_menu
    assert 'default' not in prompt_menu


@pytest.mark.parametrize('invalid', ['0', '4', '-1', 'P1', 'invalid', '1,2', '1,1'])
def test_invalid_prompt_choice_is_rejected_before_valid_selection(variants, invalid):
    _, _, text = manual(variants, ['1', '1', '1', invalid, '3', '1', '1', '', 'n'])
    assert variants.calls[0][1]['prompt_id'] == 38
    assert text.count('Select prompt') == 2
    assert 'Enter one number from this page.' in text


@pytest.mark.parametrize('back', ['q', 'back'])
def test_back_from_prompt_returns_to_case_type_then_uses_new_selection(variants, back):
    variants.data['cases'].append(dict(variants.data['cases'][0], id=12,
        case_code='FAULT', reference=['FAIL', 'NOT_APPLICABLE', 'NOT_APPLICABLE']))
    _, _, text = manual(variants, ['1', '1', '1', back, '2', '3', '1', '1', '', 'n'])
    assert variants.calls[0][1]['case_id'] == 12
    assert variants.calls[0][1]['prompt_id'] == 38
    assert text.count('Choose case type') == 2
    assert text.count('Select prompt') == 2
    assert text.count('Select case\n') == 1


@pytest.mark.parametrize('back', ['q', 'back'])
def test_back_from_case_returns_to_prompt_and_replaces_previous_choice(variants, back):
    _, _, text = manual(variants, ['1', '1', '1', '3', back, '1', '1', '1', '', 'n'])
    assert variants.calls[0][1]['prompt_id'] == 12
    assert text.count('Choose case type') == 1
    assert text.count('Select prompt') == 2
    assert text.count('Select case\n') == 2
    assert 'P1' in text.split('Ready to run', 1)[1]


@pytest.mark.parametrize('available,choice,expected_id', [
    (['P2'], '', 25), (['P1', 'P3'], '', 12), (['P3'], '1', 38),
])
def test_only_catalog_prompts_are_offered(variants, available, choice, expected_id):
    variants.data['prompts'] = [row for row in variants.data['prompts'] if row['name'] in available]
    _, _, text = manual(variants, ['1', '1', '1', choice, '1', '1', '', 'n'])
    assert variants.calls[0][1]['prompt_id'] == expected_id
    prompt_menu = text.split('Select prompt', 1)[1].split('Select case', 1)[0]
    for name in ('P1', 'P2', 'P3'):
        assert (name in prompt_menu) is (name in available)


def test_empty_prompt_catalog_blocks_before_case_selection_or_plan(variants):
    variants.data['prompts'] = []
    with pytest.raises(ValueError, match='prompt'):
        manual(variants, ['1', '1', '1'])
    assert variants.calls == []


@pytest.mark.parametrize('exception', [EOFError, KeyboardInterrupt])
@pytest.mark.parametrize('prefix', [['1', '1', '1'], ['1', '1', '1', '2']])
def test_interrupt_at_prompt_or_case_never_plans(variants, exception, prefix):
    parsed = args()
    parsed.adhoc = True
    view, _ = console()
    answers = iter(prefix)

    def interrupted(_):
        try:
            return next(answers)
        except StopIteration:
            raise exception()

    value, code = live_demo_cli.run(object(), parsed, view,
        input_fn=interrupted, interactive=True)
    assert code == 130 and value['status'] == 'CANCELLED'
    assert variants.calls == []


def test_back_through_prompt_and_parent_menus_never_plans(variants):
    value, code, _ = manual(variants, ['1', '1', '1', '3', 'q', 'q', 'q', 'q', 'q'])
    assert code == 0 and value['status'] == 'CANCELLED'
    assert variants.calls == []


def test_selection_returns_actual_catalog_prompt_row(variants):
    parsed = args('--repetitions', '1')
    parsed.adhoc = True
    view, _ = console()
    answers = iter(['1', '1', '1', '3', '1', '1'])
    case, models, repetitions, runtime, prompt = live_demo_cli._selection(
        object(), parsed, view, lambda _: next(answers), True)
    assert case is variants.data['cases'][0]
    assert models == [variants.data['models'][0]] and repetitions == 1 and runtime is None
    assert prompt is variants.data['prompts'][0]
    assert prompt['id'] == 38 and variants.calls == []


@pytest.mark.parametrize('adhoc', [False, True])
@pytest.mark.parametrize('interactive', [False, True])
def test_explicit_case_keeps_existing_default_without_prompt_menu(variants, adhoc, interactive):
    parsed = args('--case-id', '11', '--model-id', '4', '--repetitions', '1', '--dry-run')
    parsed.adhoc = adhoc
    view, output = console()
    value, code = live_demo_cli.run(object(), parsed, view, input_fn=no_input, interactive=interactive)
    assert code == 0 and value['status'] == 'DRY RUN'
    assert value['plan']['prompt'] == 'P2' and value['plan']['prompt_id'] == 25
    assert 'prompt_id' not in variants.calls[0][1]
    assert [call for call, _ in variants.calls] == ['plan']
    assert 'Select prompt' not in output.getvalue()


def test_strict_interactive_demo_keeps_default_without_new_selection(variants):
    view, output = console()
    answers = iter(['1', '1', '1', '1', '', 'n'])
    value, code = live_demo_cli.run(object(), args(), view,
        input_fn=lambda _: next(answers), interactive=True)
    assert code == 0 and value['status'] == 'CANCELLED'
    assert 'prompt_id' not in variants.calls[0][1]
    assert 'Select prompt' not in output.getvalue()
    assert 'P2 (unchanged)' in output.getvalue()
