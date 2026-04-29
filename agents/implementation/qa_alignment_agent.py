"""QA alignment agent for final quality summary and change-log generation."""

from __future__ import annotations

from clients.llm import LLMClient
from schemas.implementation.qa_alignment import QAAlignmentInput, QAAlignmentOutput

from agents.implementation.helpers import dump_model, load_prompt_text, make_label


def run_qa_alignment_agent(
    input_model: QAAlignmentInput,
    llm_client: LLMClient,
) -> QAAlignmentOutput:
    """Review all upstream outputs and produce the final QA/alignment summary."""
    _ = llm_client
    _ = load_prompt_text
    _ = dump_model

    content_output = input_model.content_interaction_output
    item_count = len(content_output.items)
    quiz_type_count = len(content_output.quiz_types)
    interaction_mode = content_output.interaction_mode or "quiz"
    interaction_mode_reason = content_output.interaction_mode_reason or "not provided"
    interaction_units = content_output.interaction_units
    interaction_unit_count = len(interaction_units)
    interaction_validation = content_output.interaction_validation
    interaction_type_counts = (
        interaction_validation.unit_type_counts
        if interaction_validation is not None
        else {}
    )
    interaction_distribution = _describe_interaction_distribution(
        interaction_type_counts=interaction_type_counts,
    )
    quiz_backward_compat = item_count > 0
    implementation_spec = input_model.implementation_spec
    expected_total = implementation_spec.total_count if implementation_spec else item_count
    configured_content_types = (
        implementation_spec.core_features
        if implementation_spec and implementation_spec.core_features
        else content_output.quiz_types
    )
    expected_quiz_type_count = len(configured_content_types)
    quiz_type_counts = {
        quiz_type: sum(1 for item in content_output.items if item.quiz_type == quiz_type)
        for quiz_type in configured_content_types
    }
    quest_session_shape = _describe_content_shape(
        configured_content_types=configured_content_types,
        quiz_type_counts=quiz_type_counts,
    )
    semantic_summary = content_output.semantic_validation
    issues = list(input_model.run_test_and_fix_output.remaining_risks)
    if interaction_validation is None:
        issues.append("Interaction validation summary is missing from content output.")
    elif not interaction_validation.structure_valid:
        issues.append("Interaction-unit structural validation did not fully pass.")

    if interaction_mode == "quiz" and item_count != expected_total:
        issues.append(f"Expected {expected_total} quiz items but found {item_count}.")
    if interaction_mode == "quiz" and quiz_type_count != expected_quiz_type_count:
        issues.append(
            f"Expected {expected_quiz_type_count} configured content types but found {quiz_type_count}."
        )
    if interaction_mode == "quiz" and semantic_summary is None:
        issues.append("Semantic validation summary is missing from quiz_contents output.")

    quiz_type_balance_ok = bool(semantic_summary and semantic_summary.quiz_type_distribution_valid)
    learning_dimension_ok = bool(semantic_summary and semantic_summary.learning_dimension_values_valid)
    semantic_validator_ok = bool(semantic_summary and semantic_summary.semantic_validator_passed)
    regeneration_count = semantic_summary.regeneration_count if semantic_summary else 0
    streamlit_smoke_ran = "streamlit_smoke" in input_model.run_test_and_fix_output.checks_run
    streamlit_smoke_failed = any(
        failure.check_name == "streamlit_smoke"
        for failure in input_model.run_test_and_fix_output.failures
    )
    streamlit_smoke_passed = streamlit_smoke_ran and not streamlit_smoke_failed
    package_pytest_ran = "package_pytest" in input_model.run_test_and_fix_output.checks_run
    package_pytest_failed = any(
        failure.check_name == "package_pytest"
        for failure in input_model.run_test_and_fix_output.failures
    )
    package_pytest_passed = package_pytest_ran and not package_pytest_failed

    if interaction_mode == "quiz" and not quiz_type_balance_ok:
        issues.append("Quiz type distribution does not match the configured content shape.")
    if interaction_mode == "quiz" and not learning_dimension_ok:
        issues.append("One or more learning_dimension values are invalid.")
    if interaction_mode == "quiz" and not semantic_validator_ok:
        issues.append("Semantic validator did not fully pass.")
    if streamlit_smoke_ran and not streamlit_smoke_passed:
        issues.append("Streamlit smoke test did not pass.")
    if package_pytest_ran and not package_pytest_passed:
        issues.append("Planning package pytest.py contract check did not pass.")
    if input_model.prototype_builder_output.fallback_used:
        issues.append(
            "LLM-generated app.py did not complete successfully; fallback template was used."
        )

    return QAAlignmentOutput(
        agent=make_label(
            "QA & Alignment Agent",
            "최종 검수·정합성 확인 Agent",
        ),
        alignment_status="PASS" if not issues else "WARN",
        qa_checklist=[
            f"interaction_mode 확인: {interaction_mode}",
            f"interaction_mode 추론 이유: {interaction_mode_reason}",
            f"interaction_units 수 확인: {interaction_unit_count}",
            f"interaction_type 분포 확인: {interaction_distribution}",
            f"QuizItem 하위 호환 사용 여부: {'YES' if quiz_backward_compat else 'NO'}",
            (
                f"총 문제 수 확인: {item_count}"
                if interaction_mode == 'quiz'
                else "총 문제 수 확인: N/A (interaction-unit primary mode)"
            ),
            (
                f"세션 구성 확인: {quest_session_shape}"
                if interaction_mode == 'quiz'
                else "세션 구성 확인: interaction_units 순서와 next_step 기준"
            ),
            (
                f"configured content type 수({expected_quiz_type_count}) 일치 여부: "
                f"{'PASS' if quiz_type_balance_ok else 'FAIL'}"
                if interaction_mode == "quiz"
                else "N/A (interaction-unit primary mode)"
            ),
            (
                f"learning_dimension 허용값 여부: {'PASS' if learning_dimension_ok else 'FAIL'}"
                if interaction_mode == "quiz"
                else "learning_dimension 허용값 여부: N/A (quiz semantic validator not required)"
            ),
            (
                f"semantic validator 통과 여부: {'PASS' if semantic_validator_ok else 'FAIL'}"
                if interaction_mode == "quiz"
                else "semantic validator 통과 여부: N/A (interaction-unit primary mode)"
            ),
            (
                f"재생성 발생 여부: {'YES' if regeneration_count else 'NO'}"
                if interaction_mode == "quiz"
                else "재생성 발생 여부: N/A (quiz regeneration path not used)"
            ),
            (
                "interaction_units 구조 validator 통과 여부: "
                f"{'PASS' if interaction_validation and interaction_validation.structure_valid else 'FAIL'}"
            ),
            (
                "app.py Streamlit smoke test 여부: "
                f"{'PASS' if streamlit_smoke_passed else 'FAIL' if streamlit_smoke_ran else 'NOT RUN'}"
            ),
            (
                "package pytest.py 통과 여부: "
                f"{'PASS' if package_pytest_passed else 'FAIL' if package_pytest_ran else 'NOT RUN'}"
            ),
            (
                "Prototype Builder LLM 생성 여부: "
                f"{input_model.prototype_builder_output.generation_mode}"
            ),
            (
                "fallback template 사용 여부: "
                f"{'YES' if input_model.prototype_builder_output.fallback_used else 'NO'}"
            ),
            (
                "app.py가 서비스별 콘텐츠 파일을 읽도록 생성되었는지 확인"
            ),
            "실행 로그와 변경 로그가 생성되었는지 확인",
        ],
        qa_issues=issues,
        change_log_entries=[
            (
                "Prototype Builder Agent는 LLM 기반 app.py 생성을 우선 수행하고, "
                "실패 시에만 fallback template을 사용하도록 정리되었다."
            ),
            (
                "Content & Interaction Agent는 InteractionUnit 중심 구조를 함께 생성하며, "
                f"interaction_mode={interaction_mode}, unit_count={interaction_unit_count}, "
                f"mode_reason={interaction_mode_reason}."
            ),
            (
                "Prototype Builder generation result: "
                f"mode={input_model.prototype_builder_output.generation_mode}, "
                f"fallback_used={input_model.prototype_builder_output.fallback_used}, "
                f"errors={input_model.prototype_builder_output.builder_errors}."
            ),
            "QA & Alignment Agent는 현재 단계에서 deterministic summary를 생성한다.",
            (
                "#12 semantic validator 결과: "
                f"mode={interaction_mode}, "
                f"expected_total={expected_total}, "
                f"actual_total={item_count}, "
                f"configured_content_types={expected_quiz_type_count}, "
                f"content_types_valid={quiz_type_balance_ok if interaction_mode == 'quiz' else 'N/A'}, "
                f"learning_dimension_valid={learning_dimension_ok if interaction_mode == 'quiz' else 'N/A'}, "
                f"semantic_validator_passed={semantic_validator_ok if interaction_mode == 'quiz' else 'N/A'}, "
                f"regeneration_count={regeneration_count if interaction_mode == 'quiz' else 'N/A'}, "
                f"interaction_structure_valid={interaction_validation.structure_valid if interaction_validation else False}, "
                f"streamlit_smoke={'PASS' if streamlit_smoke_passed else 'FAIL' if streamlit_smoke_ran else 'NOT RUN'}, "
                f"package_pytest={'PASS' if package_pytest_passed else 'FAIL' if package_pytest_ran else 'NOT RUN'}."
            ),
        ],
        final_summary_points=[
            "교육 서비스 구현팀 6-Agent 파이프라인이 실행되었다.",
            (
                f"{quiz_type_count}개 content type, 총 {item_count}문항이 생성되었다."
                if interaction_mode == "quiz"
                else f"{interaction_unit_count}개 interaction unit이 생성되었다."
            ),
            (
                f"세션 구성: {quest_session_shape}."
                if interaction_mode == "quiz"
                else f"상호작용 흐름: {interaction_distribution}."
            ),
            f"interaction_mode={interaction_mode}, reason={interaction_mode_reason}.",
            (
                "#12 검증 결과: "
                f"semantic validator="
                f"{'PASS' if semantic_validator_ok else 'FAIL' if interaction_mode == 'quiz' else 'N/A'}, "
                f"interaction validator="
                f"{'PASS' if interaction_validation and interaction_validation.structure_valid else 'FAIL'}, "
                f"재생성="
                f"{'없음' if interaction_mode != 'quiz' or regeneration_count == 0 else f'{regeneration_count}건'}."
            ),
            (
                "#20 실행 검증 결과: "
                f"package_pytest={'PASS' if package_pytest_passed else 'FAIL' if package_pytest_ran else 'NOT RUN'}, "
                f"streamlit_smoke={'PASS' if streamlit_smoke_passed else 'FAIL' if streamlit_smoke_ran else 'NOT RUN'}."
            ),
            (
                "#28 Prototype Builder 결과: "
                f"generation_mode={input_model.prototype_builder_output.generation_mode}, "
                f"fallback={'YES' if input_model.prototype_builder_output.fallback_used else 'NO'}, "
                f"reflection_attempts={input_model.prototype_builder_output.reflection_attempts}."
            ),
            "Streamlit MVP, 실행 로그, QA 결과가 함께 정리되었다.",
        ],
    )


def _describe_content_shape(
    *,
    configured_content_types: list[str],
    quiz_type_counts: dict[str, int],
) -> str:
    if not configured_content_types:
        return "configured content type 없음"
    parts = [
        f"{quiz_type} {quiz_type_counts.get(quiz_type, 0)}"
        for quiz_type in configured_content_types
    ]
    return " + ".join(parts)


def _describe_interaction_distribution(*, interaction_type_counts: dict[str, int]) -> str:
    if not interaction_type_counts:
        return "interaction_type 없음"
    return " + ".join(
        f"{interaction_type} {count}"
        for interaction_type, count in sorted(interaction_type_counts.items())
    )
