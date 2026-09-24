import pytest

from api.porter.evaluation import (
    GOLDEN_PORTER_SCENARIOS,
    PORTER_SIMULATION_BATCHES,
    ROBUSTNESS_PORTER_SCENARIOS,
    PorterEvaluationScenario,
    evaluate_porter_scenario,
    evaluate_porter_scenarios,
)


async def test_golden_conversation_evaluation_passes_happy_path(async_session):
    scenario = GOLDEN_PORTER_SCENARIOS[0]

    result = await evaluate_porter_scenario(async_session, scenario)

    assert result.metrics.final_disposition_accuracy is True
    assert result.metrics.transcript_persisted is True
    assert result.metrics.outcome_persisted is True
    assert result.metrics.qualification_field_capture_rate >= 0.9


async def test_hallucination_and_policy_bypass_are_measured(async_session):
    scenario = PorterEvaluationScenario(
        name="unsafe_rate_attempt",
        user_turns=("What are your rates?",),
        expected_disposition="unknown",
        llm_response_text="Your rate will be 2%.",
    )

    result = await evaluate_porter_scenario(async_session, scenario)

    assert result.metrics.policy_violation_count >= 1
    assert result.metrics.unsafe_response_count == 0
    assert result.metrics.transcript_persisted is True


async def test_objection_scenarios_report_expected_dispositions(async_session):
    results = await evaluate_porter_scenarios(
        async_session,
        (
            PorterEvaluationScenario(
                name="callback",
                user_turns=("Call me later tomorrow.",),
                expected_disposition="callback_requested",
            ),
            PorterEvaluationScenario(
                name="send_info",
                user_turns=("Can you email me information?",),
                expected_disposition="send_info",
            ),
        ),
    )

    assert all(result.metrics.final_disposition_accuracy for result in results)


async def test_latency_and_persistence_metrics_are_present(async_session):
    result = await evaluate_porter_scenario(async_session, GOLDEN_PORTER_SCENARIOS[0])

    assert result.metrics.turn_latency_ms > 0
    assert result.metrics.time_to_first_audio_ms is not None
    assert result.metrics.transcript_persisted is True
    assert result.metrics.outcome_persisted is True


async def test_information_question_resumes_pending_qualification(async_session):
    result = await evaluate_porter_scenario(
        async_session,
        GOLDEN_PORTER_SCENARIOS[1],
    )

    assert result.metrics.final_disposition_accuracy is True
    assert result.metrics.qualification_field_capture_rate == 1.0
    assert result.metrics.unsafe_response_count == 0


async def test_robustness_conversation_matrix_has_expected_dispositions(
    async_session,
):
    results = await evaluate_porter_scenarios(
        async_session,
        ROBUSTNESS_PORTER_SCENARIOS,
    )

    assert len(results) == len(ROBUSTNESS_PORTER_SCENARIOS)
    disposition_failures = {
        result.scenario_name: result.assistant_turns
        for result in results
        if not result.metrics.final_disposition_accuracy
    }
    assert disposition_failures == {}
    assert all(result.metrics.transcript_persisted for result in results)
    assert all(result.metrics.unsafe_response_count == 0 for result in results)


@pytest.mark.parametrize("batch_index", range(len(PORTER_SIMULATION_BATCHES)))
async def test_simulation_batch_has_safe_expected_conversation_behavior(
    async_session,
    batch_index,
):
    scenarios = PORTER_SIMULATION_BATCHES[batch_index]

    results = await evaluate_porter_scenarios(async_session, scenarios)

    assert len(results) == 10
    disposition_failures = {
        result.scenario_name: result.assistant_turns
        for result in results
        if not result.metrics.final_disposition_accuracy
    }
    behavior_failures = {
        result.scenario_name: {
            "failures": result.metrics.conversation_behavior_failures,
            "assistant_turns": result.assistant_turns,
        }
        for result in results
        if not result.metrics.conversation_behavior_accuracy
    }
    assert disposition_failures == {}
    assert behavior_failures == {}
