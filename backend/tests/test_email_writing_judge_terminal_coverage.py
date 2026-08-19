"""Terminal branch-coverage tests for the email-writing Judge contract."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from services.email_writing_judge import (
    EMAIL_WRITING_JUDGE_EVALUATION_ANCHORS,
    EMAIL_WRITING_JUDGE_EVALUATION_CATEGORY_COUNT,
    EmailWritingIndependentJudge,
    EmailWritingJudgeError,
    ReleasedJudgeSymbols,
    _JudgeOutputModel,
    _require_integral_category,
    build_email_writing_judge_task,
    export_judge_response_matrix,
    judge_results_to_response_rows,
    load_released_judge_symbols,
    parse_email_writing_judge_output,
    required_judge_criterion_ids,
)
from tests.test_email_writing_judge import (
    _JudgeRunner,
    _bundle,
    _diagnostic,
    _fixtures,
    _judge_json,
)


def test_empty_replacement_does_not_require_replacement_correctness() -> None:
    task = build_email_writing_judge_task(
        _diagnostic(replacement=""),
        _bundle(),
        category_count=EMAIL_WRITING_JUDGE_EVALUATION_CATEGORY_COUNT,
        category_anchors=EMAIL_WRITING_JUDGE_EVALUATION_ANCHORS,
    )
    assert task.candidate_kind == "no_replacement_diagnostic"
    assert "replacement_correctness" not in task.required_criterion_ids


def test_noncanonical_anchors_are_rejected() -> None:
    with pytest.raises(EmailWritingJudgeError) as captured:
        build_email_writing_judge_task(
            _diagnostic(),
            _bundle(),
            category_count=3,
            category_anchors=("low", "mid", "high"),
        )
    assert captured.value.code == "judge_anchors_invalid"


def test_released_symbols_load_from_an_injected_complete_module() -> None:
    class _Module:
        ContextualOrchestratorJudge = object()
        JudgeCriterion = object()
        JudgeFormatError = object()
        LLMJudgeResult = object()
        validate_irt_response_matrix = staticmethod(lambda *args, **kwargs: args[0])

    symbols = load_released_judge_symbols(module_importer=lambda _name: _Module())
    assert isinstance(symbols, ReleasedJudgeSymbols)
    assert symbols.package_name == "fast_mlsirm"


def test_incomplete_or_broken_importer_fails_closed() -> None:
    class _Partial:
        ContextualOrchestratorJudge = object()

    with pytest.raises(EmailWritingJudgeError) as captured:
        load_released_judge_symbols(module_importer=lambda _name: _Partial())
    assert captured.value.code == "judge_package_unavailable"

    def _boom(_name: str) -> object:
        raise RuntimeError("broken importer")

    with pytest.raises(EmailWritingJudgeError) as captured_boom:
        load_released_judge_symbols(module_importer=_boom)  # type: ignore[arg-type]
    assert captured_boom.value.code == "judge_package_unavailable"


def test_runner_mapping_response_is_normalized_and_empty_rows_fail() -> None:
    runner = _JudgeRunner(_fixtures()["valid_replacement_judge"])
    result = EmailWritingIndependentJudge(runner).evaluate(
        _diagnostic(),
        _bundle(),
        candidate_model_profile_id="candidate-profile",
        judge_model_profile_id="judge-profile",
    )
    assert result.user_facing_admission == "withheld"

    with pytest.raises(EmailWritingJudgeError) as captured:
        judge_results_to_response_rows(())
    assert captured.value.code == "judge_matrix_empty"


def test_invalid_runner_payload_is_rejected() -> None:
    runner = _JudgeRunner(object())
    with pytest.raises(EmailWritingJudgeError) as captured:
        EmailWritingIndependentJudge(runner).evaluate(
            _diagnostic(),
            _bundle(),
            candidate_model_profile_id="candidate-profile",
            judge_model_profile_id="judge-profile",
        )
    assert captured.value.code == "judge_payload_invalid"


@pytest.mark.parametrize(
    ("criterion_scores", "category_count"),
    [
        ({}, 4),
        ({"issue_support": True}, 4),
        ({"issue_support": "0.5"}, 4),
        ({"issue_support": 1.5}, 4),
        ({"issue_support": float("nan")}, 4),
        ({"issue_support": float("inf")}, 4),
        ({"issue_support": 0.5}, 1),
    ],
)
def test_score_model_guards_reject_invalid_tokens(
    criterion_scores: dict[str, object],
    category_count: int,
) -> None:
    with pytest.raises(ValidationError):
        _JudgeOutputModel.model_validate(
            {
                "criterion_categories": {"issue_support": 1},
                "criterion_scores": criterion_scores,
                "category_count": category_count,
                "accepted": False,
            }
        )


def test_score_and_category_type_guards_reject_bool_and_text_tokens() -> None:
    for score in (True, "0.5"):
        with pytest.raises(ValidationError, match="judge_score_type"):
            _JudgeOutputModel.model_validate(
                {
                    "criterion_categories": {"issue_support": 1},
                    "criterion_scores": {"issue_support": score},
                    "category_count": 4,
                    "accepted": False,
                }
            )
    with pytest.raises(EmailWritingJudgeError) as captured:
        _require_integral_category(True)
    assert captured.value.code == "judge_payload_invalid"
    with pytest.raises(EmailWritingJudgeError):
        _require_integral_category(1.0)
    assert _require_integral_category(2) == 2


def test_out_of_range_category_is_rejected() -> None:
    payload = {
        "criterion_categories": {
            criterion_id: 0
            for criterion_id in required_judge_criterion_ids(has_replacement=False)
        },
        "criterion_scores": {
            criterion_id: 0.0
            for criterion_id in required_judge_criterion_ids(has_replacement=False)
        },
        "category_count": 4,
        "accepted": False,
    }
    payload["criterion_categories"]["issue_support"] = 4
    with pytest.raises(EmailWritingJudgeError) as captured:
        parse_email_writing_judge_output(
            _judge_json(payload),
            required_criterion_ids=required_judge_criterion_ids(has_replacement=False),
            category_count=4,
        )
    assert captured.value.code == "judge_payload_invalid"


def test_export_uses_injected_loaded_validator() -> None:
    class _Module:
        ContextualOrchestratorJudge = object()
        JudgeCriterion = object()
        JudgeFormatError = object()
        LLMJudgeResult = object()

        @staticmethod
        def validate_irt_response_matrix(
            responses: object,
            item_type: str,
            *,
            n_categories: int | None = None,
        ) -> tuple[object, str, int | None]:
            return (responses, item_type, n_categories)

    parsed = parse_email_writing_judge_output(
        _judge_json(),
        required_criterion_ids=required_judge_criterion_ids(has_replacement=True),
        category_count=4,
    )
    rows = judge_results_to_response_rows((parsed, parsed))
    exported = export_judge_response_matrix(
        rows,
        n_categories=4,
        validator=_Module.validate_irt_response_matrix,
    )
    assert exported == (rows, "polytomous", 4)


def test_export_without_injected_validator_uses_released_symbol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fake_loader(
        *,
        module_importer: object | None = None,
    ) -> ReleasedJudgeSymbols:
        return ReleasedJudgeSymbols(
            package_name="fast_mlsirm",
            contextual_orchestrator_judge=object(),
            judge_criterion=object(),
            judge_format_error=object(),
            llm_judge_result=object(),
            validate_irt_response_matrix=lambda responses, item_type, *, n_categories=None: (
                "released",
                responses,
                item_type,
                n_categories,
            ),
        )

    monkeypatch.setattr(
        "services.email_writing_judge.load_released_judge_symbols",
        _fake_loader,
    )
    parsed = parse_email_writing_judge_output(
        _judge_json(),
        required_criterion_ids=required_judge_criterion_ids(has_replacement=True),
        category_count=4,
    )
    rows = judge_results_to_response_rows((parsed, parsed))
    exported = export_judge_response_matrix(rows, n_categories=4)
    assert exported == ("released", rows, "polytomous", 4)
