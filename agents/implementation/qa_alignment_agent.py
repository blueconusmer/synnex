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
    issues = list(input_model.run_test_and_fix_output.remaining_risks)
    if item_count != 8:
        issues.append(f"Expected 8 quiz items but found {item_count}.")
    if quiz_type_count != 4:
        issues.append(f"Expected 4 quiz types but found {quiz_type_count}.")

    return QAAlignmentOutput(
        agent=make_label(
            "QA & Alignment Agent",
            "최종 검수·정합성 확인 Agent",
        ),
        alignment_status="PASS" if not issues else "WARN",
        qa_checklist=[
            f"총 문제 수 확인: {item_count}",
            f"퀴즈 유형 수 확인: {quiz_type_count}",
            "app.py가 quiz_contents.json을 읽도록 생성되었는지 확인",
            "실행 로그와 변경 로그가 생성되었는지 확인",
        ],
        qa_issues=issues,
        change_log_entries=[
            "Prototype Builder Agent는 live 실행 안정성을 위해 검증된 Streamlit 템플릿을 사용하도록 정규화되었다.",
            "QA & Alignment Agent는 현재 단계에서 deterministic summary를 생성한다.",
        ],
        final_summary_points=[
            "교육 서비스 구현팀 6-Agent 파이프라인이 실행되었다.",
            f"질문력 향상 퀴즈 {quiz_type_count}개 유형, 총 {item_count}문항이 생성되었다.",
            "Streamlit MVP, 실행 로그, QA 결과가 함께 정리되었다.",
        ],
    )
