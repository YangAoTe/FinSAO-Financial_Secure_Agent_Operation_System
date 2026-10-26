from banking_dataset.generate import generate
from banking_dataset.score import Prediction, score
from banking_dataset.validate import validate


def test_generated_dataset_has_expected_size_and_no_trusted_arguments() -> None:
    rows = generate()
    assert len(rows) == 1000
    assert {row.split for row in rows} == {"train", "dev", "test"}
    assert all(
        "authorization_ref" not in call.key_arguments
        for row in rows
        for call in row.expected_tool_calls
    )


def test_written_dataset_validates_without_split_leakage() -> None:
    result = validate()
    assert result["valid_rows"] == 1000
    assert result["exact_cross_split_leaks"] == 0
    assert result["tool_schema_alignment"] is True
    assert result["second_human_review_complete"] is True


def test_scorer_reports_per_dimension_metrics() -> None:
    sample = generate()[0]
    prediction = Prediction(
        sample_id=sample.sample_id,
        intent=sample.intent,
        tool_names=[call.tool_name for call in sample.expected_tool_calls],
        risk_tier=sample.expected_risk_tier,
        requires_clarification=sample.requires_clarification,
        safety_expectation=sample.safety_expectation,
    )
    result = score([sample], [prediction])
    assert result["intent_macro_f1"] == 1.0
    assert result["tool_sequence_accuracy"] == 1.0
    assert result["safety_accuracy"] == 1.0
