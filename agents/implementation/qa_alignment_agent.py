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

    item_count = len(input_model.content_interaction_output.items)
    quiz_type_count = len(input_model.content_interaction_output.quiz_types)
    implementation_spec = input_model.implementation_spec
    expected_total = implementation_spec.total_count if implementation_spec else item_count
    configured_content_types = (
        implementation_spec.core_features
        if implementation_spec and implementation_spec.core_features
        else input_model.content_interaction_output.quiz_types
    )
    expected_quiz_type_count = len(configured_content_types)
    quiz_type_counts = {
        quiz_type: sum(
            1 for item in input_model.content_interaction_output.items if item.quiz_type == quiz_type
        )
        for quiz_type in configured_content_types
    }
    quest_session_shape = _describe_content_shape(
        configured_content_types=configured_content_types,
        quiz_type_counts=quiz_type_counts,
    )
    semantic_summary = input_model.content_interaction_output.semantic_validation
    issues = list(input_model.run_test_and_fix_output.remaining_risks)
    if item_count != expected_total:
        issues.append(f"Expected {expected_total} quiz items but found {item_count}.")
    if quiz_type_count != expected_quiz_type_count:
        issues.append(
            f"Expected {expected_quiz_type_count} configured content types but found {quiz_type_count}."
        )
    if semantic_summary is None:
        issues.append("Semantic validation summary is missing from quiz_contents output.")

    quiz_type_balance_ok = bool(
        semantic_summary and semantic_summary.quiz_type_distribution_valid
    )
    learning_dimension_ok = bool(
        semantic_summary and semantic_summary.learning_dimension_values_valid
    )
    semantic_validator_ok = bool(
        semantic_summary and semantic_summary.semantic_validator_passed
    )
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

    if not quiz_type_balance_ok:
        issues.append("Quiz type distribution does not match the configured content shape.")
    if not learning_dimension_ok:
        issues.append("One or more learning_dimension values are invalid.")
    if not semantic_validator_ok:
        issues.append("Semantic validator did not fully pass.")
    if streamlit_smoke_ran and not streamlit_smoke_passed:
        issues.append("Streamlit smoke test did not pass.")
    if package_pytest_ran and not package_pytest_passed:
        issues.append("Planning package pytest.py contract check did not pass.")

    return QAAlignmentOutput(
        agent=make_label(
            "QA & Alignment Agent",
            "최종 검수·정합성 확인 Agent",
        ),
        alignment_status="PASS" if not issues else "WARN",
        qa_checklist=[
            f"총 문제 수 확인: {item_count}",
            f"세션 구성 확인: {quest_session_shape}",
            (
                f"configured content type 수({expected_quiz_type_count}) 일치 여부: "
                f"{'PASS' if quiz_type_balance_ok else 'FAIL'}"
            ),
            f"learning_dimension 허용값 여부: {'PASS' if learning_dimension_ok else 'FAIL'}",
            f"semantic validator 통과 여부: {'PASS' if semantic_validator_ok else 'FAIL'}",
            f"재생성 발생 여부: {'YES' if regeneration_count else 'NO'}",
            (
                "app.py Streamlit smoke test 여부: "
                f"{'PASS' if streamlit_smoke_passed else 'FAIL' if streamlit_smoke_ran else 'NOT RUN'}"
            ),
            (
                "package pytest.py 통과 여부: "
                f"{'PASS' if package_pytest_passed else 'FAIL' if package_pytest_ran else 'NOT RUN'}"
            ),
            (
                "app.py가 서비스별 콘텐츠 파일을 읽도록 생성되었는지 확인"
            ),
            "실행 로그와 변경 로그가 생성되었는지 확인",
        ],
        qa_issues=issues,
        change_log_entries=[
            "Prototype Builder Agent는 live 실행 안정성을 위해 검증된 Streamlit 템플릿을 사용하도록 정규화되었다.",
            "QA & Alignment Agent는 현재 단계에서 deterministic summary를 생성한다.",
            (
                "#12 semantic validator 결과: "
                f"expected_total={expected_total}, "
                f"actual_total={item_count}, "
                f"configured_content_types={expected_quiz_type_count}, "
                f"content_types_valid={quiz_type_balance_ok}, "
                f"learning_dimension_valid={learning_dimension_ok}, "
                f"semantic_validator_passed={semantic_validator_ok}, "
                f"regeneration_count={regeneration_count}, "
                f"streamlit_smoke={'PASS' if streamlit_smoke_passed else 'FAIL' if streamlit_smoke_ran else 'NOT RUN'}, "
                f"package_pytest={'PASS' if package_pytest_passed else 'FAIL' if package_pytest_ran else 'NOT RUN'}."
            ),
        ],
        final_summary_points=[
            "교육 서비스 구현팀 6-Agent 파이프라인이 실행되었다.",
            f"{quiz_type_count}개 content type, 총 {item_count}문항이 생성되었다.",
            f"세션 구성: {quest_session_shape}.",
            (
                "#12 검증 결과: "
                f"semantic validator={'PASS' if semantic_validator_ok else 'FAIL'}, "
                f"재생성={'없음' if regeneration_count == 0 else f'{regeneration_count}건'}."
            ),
            (
                "#20 실행 검증 결과: "
                f"package_pytest={'PASS' if package_pytest_passed else 'FAIL' if package_pytest_ran else 'NOT RUN'}, "
                f"streamlit_smoke={'PASS' if streamlit_smoke_passed else 'FAIL' if streamlit_smoke_ran else 'NOT RUN'}."
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
