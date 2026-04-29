from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from clients.llm import LLMClient
from schemas.implementation.content_interaction import ContentInteractionOutput
from schemas.implementation.implementation_spec import ImplementationSpec
from schemas.implementation.orchestration_decision import (
    OrchestrationDecision,
    OrchestrationJudgeOutput,
    RetryInstruction,
)
from schemas.implementation.prototype_builder import PrototypeBuilderOutput
from schemas.implementation.qa_alignment import QAAlignmentOutput
from schemas.implementation.requirement_mapping import RequirementMappingOutput
from schemas.implementation.run_test_and_fix import RunTestAndFixOutput
from schemas.implementation.spec_intake import SpecIntakeOutput
from schemas.planning_package import InputIntakeResult

from agents.implementation.helpers import dump_model, load_prompt_text


TARGET_SPEC = "SPEC_INTAKE"
TARGET_REQUIREMENT = "REQUIREMENT_MAPPING"
TARGET_CONTENT = "CONTENT_INTERACTION"
TARGET_NONE = "NONE"
TARGET_HUMAN = "HUMAN_REVIEW"


@dataclass
class RoutingSignals:
    spec_summary_weak: bool = False
    requirements_weak: bool = False
    content_contract_weak: bool = False
    requirements_flow_hints_missing: bool = False
    content_flow_hints_missing: bool = False
    builder_fallback_used: bool = False
    builder_flow_not_reflected: bool = False
    runtime_failed: bool = False
    code_only_runtime_failure: bool = False
    qa_warn_alignment: bool = False
    evidence: list[str] = field(default_factory=list)


def build_orchestration_decision(
    *,
    llm_client: LLMClient,
    implementation_spec: ImplementationSpec,
    input_intake_result: InputIntakeResult | None,
    spec_intake_output: SpecIntakeOutput,
    requirement_mapping_output: RequirementMappingOutput,
    content_interaction_output: ContentInteractionOutput,
    prototype_builder_output: PrototypeBuilderOutput,
    run_test_and_fix_output: RunTestAndFixOutput,
    qa_alignment_output: QAAlignmentOutput,
    retry_count: int = 0,
    max_retry_count: int = 3,
) -> OrchestrationDecision:
    signals = _collect_signals(
        implementation_spec=implementation_spec,
        spec_intake_output=spec_intake_output,
        requirement_mapping_output=requirement_mapping_output,
        content_interaction_output=content_interaction_output,
        prototype_builder_output=prototype_builder_output,
        run_test_and_fix_output=run_test_and_fix_output,
        qa_alignment_output=qa_alignment_output,
    )

    if signals.code_only_runtime_failure:
        return OrchestrationDecision(
            overall_status="OUT_OF_SCOPE",
            issue_type="APP_GENERATION_FEEDBACK",
            observed_stage=_observed_stage(
                prototype_builder_output=prototype_builder_output,
                run_test_and_fix_output=run_test_and_fix_output,
                qa_alignment_output=qa_alignment_output,
            ),
            target_agent=TARGET_NONE,
            candidate_agents=[TARGET_NONE],
            reason="Code-only runtime failure was observed. This is not an upstream interpretation retry target.",
            recommended_action="Keep this issue in the existing Builder / Run Test And Fix path.",
            retry_required=False,
            retry_instruction=RetryInstruction(),
            llm_judge_used=False,
            llm_judge_status="NOT_USED",
            retry_count=retry_count,
            max_retry_count=max_retry_count,
            should_stop=True,
            stop_reason="Code-only runtime failure is out of scope for the upstream feedback loop.",
        )

    direct_candidates = _collect_direct_candidates(signals)
    observed_stage = _observed_stage(
        prototype_builder_output=prototype_builder_output,
        run_test_and_fix_output=run_test_and_fix_output,
        qa_alignment_output=qa_alignment_output,
    )

    if not _needs_feedback_loop(signals, direct_candidates):
        return OrchestrationDecision(
            overall_status="PASS",
            issue_type="NONE",
            observed_stage=observed_stage,
            target_agent=TARGET_NONE,
            candidate_agents=[TARGET_NONE],
            reason="No upstream interpretation issue required a retry.",
            recommended_action="Proceed with the current outputs.",
            retry_required=False,
            retry_instruction=RetryInstruction(),
            llm_judge_used=False,
            llm_judge_status="NOT_USED",
            retry_count=retry_count,
            max_retry_count=max_retry_count,
            should_stop=True,
            stop_reason="No retry required.",
        )

    if signals.builder_fallback_used and not (
        signals.builder_flow_not_reflected or signals.qa_warn_alignment or direct_candidates
    ):
        return OrchestrationDecision(
            overall_status="OUT_OF_SCOPE",
            issue_type="APP_GENERATION_FEEDBACK",
            observed_stage=observed_stage,
            target_agent=TARGET_NONE,
            candidate_agents=[TARGET_NONE],
            reason=(
                "Prototype Builder fallback was used, but there was not enough evidence that an "
                "upstream interpretation retry would help."
            ),
            recommended_action="Keep this issue in the existing Builder / Run Test And Fix path.",
            retry_required=False,
            retry_instruction=RetryInstruction(),
            llm_judge_used=False,
            llm_judge_status="NOT_USED",
            retry_count=retry_count,
            max_retry_count=max_retry_count,
            should_stop=True,
            stop_reason="Fallback alone was not enough evidence for an upstream retry.",
        )

    if signals.builder_fallback_used or signals.builder_flow_not_reflected or signals.qa_warn_alignment:
        candidates = _collect_app_feedback_candidates(signals, direct_candidates)
        if len(candidates) == 1:
            target = candidates[0]
            return _build_retry_decision(
                issue_type="APP_GENERATION_FEEDBACK",
                observed_stage=observed_stage,
                target_agent=target,
                candidate_agents=candidates,
                reason=_build_app_feedback_reason(signals, target),
                retry_instruction=_build_retry_instruction(
                    issue_type="APP_GENERATION_FEEDBACK",
                    target_agent=target,
                    implementation_spec=implementation_spec,
                    input_intake_result=input_intake_result,
                    signals=signals,
                ),
                retry_count=retry_count,
                max_retry_count=max_retry_count,
            )
        return _resolve_ambiguous_with_judge(
            llm_client=llm_client,
            implementation_spec=implementation_spec,
            input_intake_result=input_intake_result,
            spec_intake_output=spec_intake_output,
            requirement_mapping_output=requirement_mapping_output,
            content_interaction_output=content_interaction_output,
            prototype_builder_output=prototype_builder_output,
            run_test_and_fix_output=run_test_and_fix_output,
            qa_alignment_output=qa_alignment_output,
            candidate_agents=candidates,
            issue_type="APP_GENERATION_FEEDBACK",
            observed_stage=observed_stage,
            retry_count=retry_count,
            max_retry_count=max_retry_count,
            evidence=signals.evidence,
        )

    if len(direct_candidates) == 1:
        target = direct_candidates[0]
        issue_type = _direct_issue_type(target)
        return _build_retry_decision(
            issue_type=issue_type,
            observed_stage=observed_stage,
            target_agent=target,
            candidate_agents=direct_candidates,
            reason=_build_direct_reason(target, signals),
            retry_instruction=_build_retry_instruction(
                issue_type=issue_type,
                target_agent=target,
                implementation_spec=implementation_spec,
                input_intake_result=input_intake_result,
                signals=signals,
            ),
            retry_count=retry_count,
            max_retry_count=max_retry_count,
        )

    return _resolve_ambiguous_with_judge(
        llm_client=llm_client,
        implementation_spec=implementation_spec,
        input_intake_result=input_intake_result,
        spec_intake_output=spec_intake_output,
        requirement_mapping_output=requirement_mapping_output,
        content_interaction_output=content_interaction_output,
        prototype_builder_output=prototype_builder_output,
        run_test_and_fix_output=run_test_and_fix_output,
        qa_alignment_output=qa_alignment_output,
        candidate_agents=direct_candidates,
        issue_type="AMBIGUOUS_ISSUE",
        observed_stage=observed_stage,
        retry_count=retry_count,
        max_retry_count=max_retry_count,
        evidence=signals.evidence,
    )


def _collect_signals(
    *,
    implementation_spec: ImplementationSpec,
    spec_intake_output: SpecIntakeOutput,
    requirement_mapping_output: RequirementMappingOutput,
    content_interaction_output: ContentInteractionOutput,
    prototype_builder_output: PrototypeBuilderOutput,
    run_test_and_fix_output: RunTestAndFixOutput,
    qa_alignment_output: QAAlignmentOutput,
) -> RoutingSignals:
    signals = RoutingSignals()

    service_summary = spec_intake_output.service_summary.strip()
    if len(service_summary) < 30:
        signals.spec_summary_weak = True
        signals.evidence.append("Spec Intake service_summary is too short for downstream interpretation.")
    if not spec_intake_output.normalized_requirements:
        signals.spec_summary_weak = True
        signals.evidence.append("Spec Intake normalized_requirements is empty.")
    if not spec_intake_output.delivery_expectations:
        signals.spec_summary_weak = True
        signals.evidence.append("Spec Intake delivery_expectations is empty.")

    if not requirement_mapping_output.implementation_targets:
        signals.requirements_weak = True
        signals.evidence.append("Requirement Mapping implementation_targets is empty.")
    if not requirement_mapping_output.file_plan:
        signals.requirements_weak = True
        signals.evidence.append("Requirement Mapping file_plan is empty.")
    if not requirement_mapping_output.app_constraints:
        signals.requirements_weak = True
        signals.evidence.append("Requirement Mapping app_constraints is empty.")
    if not requirement_mapping_output.test_strategy:
        signals.requirements_weak = True
        signals.evidence.append("Requirement Mapping test_strategy is empty.")

    app_constraints_text = " ".join(requirement_mapping_output.app_constraints).lower()
    if app_constraints_text and not any(
        marker in app_constraints_text
        for marker in ["screen", "state", "result", "feedback", "battle", "interaction", "flow"]
    ):
        signals.requirements_flow_hints_missing = True
        signals.evidence.append("Requirement Mapping app_constraints lacks explicit flow or state hints.")

    interaction_validation = content_interaction_output.interaction_validation
    if not content_interaction_output.interaction_units:
        signals.content_contract_weak = True
        signals.evidence.append("Content & Interaction interaction_units is empty.")
    if interaction_validation is None:
        signals.content_contract_weak = True
        signals.evidence.append("Content & Interaction interaction_validation is missing.")
    elif not interaction_validation.structure_valid:
        signals.content_contract_weak = True
        signals.evidence.append("Content & Interaction interaction_validation.structure_valid is false.")

    if not content_interaction_output.evaluation_rules:
        signals.content_contract_weak = True
        signals.evidence.append("Content & Interaction evaluation_rules is empty.")

    if not content_interaction_output.flow_notes:
        signals.content_flow_hints_missing = True
        signals.evidence.append("Content & Interaction flow_notes is empty.")

    interaction_types = {unit.interaction_type for unit in content_interaction_output.interaction_units}
    if interaction_types and "feedback" not in interaction_types and "coaching_feedback" not in interaction_types:
        signals.content_flow_hints_missing = True
        signals.evidence.append("Interaction units do not include feedback transitions.")
    if content_interaction_output.interaction_mode == "quiz" and "score_summary" not in interaction_types:
        signals.content_flow_hints_missing = True
        signals.evidence.append("Quiz interaction units do not include a score_summary step.")

    semantic_summary = content_interaction_output.semantic_validation
    if semantic_summary is not None and not semantic_summary.semantic_validator_passed:
        signals.content_contract_weak = True
        signals.evidence.append("Quiz semantic validation did not fully pass.")

    signals.builder_fallback_used = (
        prototype_builder_output.fallback_used
        or prototype_builder_output.generation_mode == "fallback_template"
    )
    if signals.builder_fallback_used:
        signals.evidence.append("Prototype Builder used the fallback template.")

    builder_reason = " ".join(
        [
            prototype_builder_output.fallback_reason,
            *prototype_builder_output.builder_errors,
            *prototype_builder_output.runtime_notes,
        ]
    ).lower()
    if any(
        marker in builder_reason
        for marker in [
            "state-machine marker",
            "screen_",
            "result screen",
            "battle",
            "transition",
        ]
    ):
        signals.builder_flow_not_reflected = True
        signals.evidence.append("Prototype Builder feedback indicates missing flow/state markers.")

    failed_check_names = {failure.check_name for failure in run_test_and_fix_output.failures}
    signals.runtime_failed = bool(failed_check_names)
    if failed_check_names:
        signals.evidence.append(
            "Run Test And Fix observed failures: " + ", ".join(sorted(failed_check_names))
        )

    if failed_check_names.intersection({"py_compile", "streamlit_smoke"}) and not signals.builder_fallback_used:
        signals.code_only_runtime_failure = True

    signals.qa_warn_alignment = _has_upstream_alignment_issue(qa_alignment_output.qa_issues)
    if signals.qa_warn_alignment:
        signals.evidence.append("QA alignment reported upstream-facing warnings or issues.")

    if implementation_spec.target_framework != "streamlit":
        signals.evidence.append(
            f"Implementation target framework is {implementation_spec.target_framework}."
        )

    return signals


def _collect_direct_candidates(signals: RoutingSignals) -> list[str]:
    candidates: list[str] = []
    if signals.spec_summary_weak:
        candidates.append(TARGET_SPEC)
    if signals.requirements_weak:
        candidates.append(TARGET_REQUIREMENT)
    if signals.content_contract_weak or signals.content_flow_hints_missing:
        candidates.append(TARGET_CONTENT)
    return candidates


def _collect_app_feedback_candidates(signals: RoutingSignals, direct_candidates: list[str]) -> list[str]:
    candidates = list(direct_candidates)
    if signals.requirements_flow_hints_missing and TARGET_REQUIREMENT not in candidates:
        candidates.append(TARGET_REQUIREMENT)
    if signals.content_flow_hints_missing and TARGET_CONTENT not in candidates:
        candidates.append(TARGET_CONTENT)
    if signals.spec_summary_weak and TARGET_SPEC not in candidates:
        candidates.append(TARGET_SPEC)
    if not candidates:
        candidates = [TARGET_REQUIREMENT, TARGET_CONTENT]
    return candidates


def _needs_feedback_loop(signals: RoutingSignals, direct_candidates: list[str]) -> bool:
    return bool(
        direct_candidates
        or signals.builder_fallback_used
        or signals.builder_flow_not_reflected
        or signals.qa_warn_alignment
    )


def _observed_stage(
    *,
    prototype_builder_output: PrototypeBuilderOutput,
    run_test_and_fix_output: RunTestAndFixOutput,
    qa_alignment_output: QAAlignmentOutput,
) -> str:
    if prototype_builder_output.fallback_used or prototype_builder_output.builder_errors:
        return "prototype_builder"
    if run_test_and_fix_output.failures:
        return "run_test_and_fix"
    if qa_alignment_output.qa_issues or qa_alignment_output.alignment_status != "PASS":
        return "qa_alignment"
    return "none"


def _direct_issue_type(target_agent: str) -> str:
    if target_agent == TARGET_SPEC:
        return "SPEC_INTERPRETATION_ISSUE"
    if target_agent == TARGET_REQUIREMENT:
        return "REQUIREMENT_MAPPING_ISSUE"
    return "CONTENT_INTERACTION_ISSUE"


def _build_direct_reason(target_agent: str, signals: RoutingSignals) -> str:
    if target_agent == TARGET_SPEC:
        return "Spec Intake output is too weak for downstream implementation."
    if target_agent == TARGET_REQUIREMENT:
        return "Requirement Mapping output is too weak for downstream implementation."
    return "Content & Interaction output does not satisfy downstream structural expectations."


def _build_app_feedback_reason(signals: RoutingSignals, target_agent: str) -> str:
    parts = ["Prototype Builder / QA feedback suggests an upstream contract refinement is needed."]
    if signals.builder_fallback_used:
        parts.append("Fallback template was used.")
    if signals.builder_flow_not_reflected:
        parts.append("Generated app did not reflect expected state or result flow.")
    if signals.qa_warn_alignment:
        parts.append("QA alignment warnings remain.")
    if target_agent == TARGET_REQUIREMENT and signals.requirements_flow_hints_missing:
        parts.append("Requirement-level flow constraints were too weak.")
    if target_agent == TARGET_CONTENT and signals.content_flow_hints_missing:
        parts.append("Interaction-unit flow details were too weak.")
    return " ".join(parts)


def _build_retry_decision(
    *,
    issue_type: str,
    observed_stage: str,
    target_agent: str,
    candidate_agents: list[str],
    reason: str,
    retry_instruction: RetryInstruction,
    retry_count: int,
    max_retry_count: int,
) -> OrchestrationDecision:
    return OrchestrationDecision(
        overall_status="RETRY_RECOMMENDED",
        issue_type=issue_type,
        observed_stage=observed_stage,
        target_agent=target_agent,
        candidate_agents=candidate_agents,
        reason=reason,
        recommended_action=f"Retry {target_agent} once with the structured retry instruction.",
        retry_required=True,
        retry_instruction=retry_instruction,
        llm_judge_used=False,
        llm_judge_status="NOT_USED",
        retry_count=retry_count,
        max_retry_count=max_retry_count,
        should_stop=False,
        stop_reason="",
    )


def _resolve_ambiguous_with_judge(
    *,
    llm_client: LLMClient,
    implementation_spec: ImplementationSpec,
    input_intake_result: InputIntakeResult | None,
    spec_intake_output: SpecIntakeOutput,
    requirement_mapping_output: RequirementMappingOutput,
    content_interaction_output: ContentInteractionOutput,
    prototype_builder_output: PrototypeBuilderOutput,
    run_test_and_fix_output: RunTestAndFixOutput,
    qa_alignment_output: QAAlignmentOutput,
    candidate_agents: list[str],
    issue_type: str,
    observed_stage: str,
    retry_count: int,
    max_retry_count: int,
    evidence: list[str],
) -> OrchestrationDecision:
    if not candidate_agents:
        return OrchestrationDecision(
            overall_status="NEEDS_HUMAN_REVIEW",
            issue_type="AMBIGUOUS_ISSUE",
            observed_stage=observed_stage,
            target_agent=TARGET_HUMAN,
            candidate_agents=[TARGET_HUMAN],
            reason="No viable upstream retry target could be derived.",
            recommended_action="Escalate to human review.",
            retry_required=False,
            retry_instruction=RetryInstruction(),
            llm_judge_used=False,
            llm_judge_status="NOT_USED",
            retry_count=retry_count,
            max_retry_count=max_retry_count,
            should_stop=True,
            stop_reason="No viable upstream retry target.",
        )

    prompt = load_prompt_text("orchestration_judge.md").format(
        candidate_agents=", ".join(candidate_agents),
        issue_summary=issue_type,
        evidence_summary="\n".join(f"- {item}" for item in evidence) or "- no explicit evidence",
        spec_intake_output=dump_model(spec_intake_output),
        requirement_mapping_output=dump_model(requirement_mapping_output),
        content_interaction_output=_summarize_content_for_judge(content_interaction_output),
        prototype_builder_output=dump_model(prototype_builder_output),
        run_test_and_fix_output=dump_model(run_test_and_fix_output),
        qa_alignment_output=dump_model(qa_alignment_output),
    )
    try:
        judge_output = llm_client.generate_json(
            prompt=prompt,
            response_model=OrchestrationJudgeOutput,
            system_prompt=(
                "You are an orchestration judge for an education-service implementation pipeline. "
                "Choose only one upstream retry target or HUMAN_REVIEW."
            ),
        )
    except Exception as exc:
        return OrchestrationDecision(
            overall_status="NEEDS_HUMAN_REVIEW",
            issue_type="AMBIGUOUS_ISSUE",
            observed_stage=observed_stage,
            target_agent=TARGET_HUMAN,
            candidate_agents=_normalize_candidates(candidate_agents),
            reason=f"LLM judge failed: {exc}",
            recommended_action="Escalate to human review.",
            retry_required=False,
            retry_instruction=RetryInstruction(),
            llm_judge_used=True,
            llm_judge_status="FAILED",
            retry_count=retry_count,
            max_retry_count=max_retry_count,
            should_stop=True,
            stop_reason="LLM judge failed.",
        )

    chosen = judge_output.chosen_target_agent
    if chosen not in {TARGET_SPEC, TARGET_REQUIREMENT, TARGET_CONTENT, TARGET_HUMAN}:
        return OrchestrationDecision(
            overall_status="NEEDS_HUMAN_REVIEW",
            issue_type="AMBIGUOUS_ISSUE",
            observed_stage=observed_stage,
            target_agent=TARGET_HUMAN,
            candidate_agents=_normalize_candidates(candidate_agents),
            reason=f"LLM judge returned an invalid target: {chosen}",
            recommended_action="Escalate to human review.",
            retry_required=False,
            retry_instruction=RetryInstruction(),
            llm_judge_used=True,
            llm_judge_status="INVALID_OUTPUT",
            retry_count=retry_count,
            max_retry_count=max_retry_count,
            should_stop=True,
            stop_reason="LLM judge returned an invalid target.",
        )

    if chosen == TARGET_HUMAN:
        return OrchestrationDecision(
            overall_status="NEEDS_HUMAN_REVIEW",
            issue_type="AMBIGUOUS_ISSUE",
            observed_stage=observed_stage,
            target_agent=TARGET_HUMAN,
            candidate_agents=_normalize_candidates(candidate_agents),
            reason=judge_output.reason,
            recommended_action="Escalate to human review.",
            retry_required=False,
            retry_instruction=judge_output.retry_instruction,
            llm_judge_used=True,
            llm_judge_status="SUCCESS",
            retry_count=retry_count,
            max_retry_count=max_retry_count,
            should_stop=True,
            stop_reason="Judge selected human review.",
        )

    return OrchestrationDecision(
        overall_status="RETRY_RECOMMENDED",
        issue_type=issue_type,
        observed_stage=observed_stage,
        target_agent=chosen,
        candidate_agents=_normalize_candidates(candidate_agents),
        reason=judge_output.reason,
        recommended_action=f"Retry {chosen} with the judge-generated instruction.",
        retry_required=True,
        retry_instruction=judge_output.retry_instruction,
        llm_judge_used=True,
        llm_judge_status="SUCCESS",
        retry_count=retry_count,
        max_retry_count=max_retry_count,
        should_stop=False,
        stop_reason="",
    )


def _normalize_candidates(candidate_agents: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    for candidate in candidate_agents:
        if candidate not in normalized:
            normalized.append(candidate)
    return normalized


def _summarize_content_for_judge(content_interaction_output: ContentInteractionOutput) -> str:
    summary = {
        "interaction_mode": content_interaction_output.interaction_mode,
        "interaction_mode_reason": content_interaction_output.interaction_mode_reason,
        "interaction_units_count": len(content_interaction_output.interaction_units),
        "flow_notes": content_interaction_output.flow_notes,
        "evaluation_rule_keys": sorted(content_interaction_output.evaluation_rules.keys()),
        "interaction_validation": (
            content_interaction_output.interaction_validation.model_dump(mode="json")
            if content_interaction_output.interaction_validation is not None
            else None
        ),
        "semantic_validation": (
            content_interaction_output.semantic_validation.model_dump(mode="json")
            if content_interaction_output.semantic_validation is not None
            else None
        ),
    }
    from json import dumps

    return dumps(summary, ensure_ascii=False, indent=2)


def _build_retry_instruction(
    *,
    issue_type: str,
    target_agent: str,
    implementation_spec: ImplementationSpec,
    input_intake_result: InputIntakeResult | None,
    signals: RoutingSignals,
) -> RetryInstruction:
    preserve_constraints = [
        f"service_name={implementation_spec.service_name}",
        f"target_framework={implementation_spec.target_framework}",
        f"total_count={implementation_spec.total_count}",
    ]
    if implementation_spec.core_features:
        preserve_constraints.append(
            "core_features=" + ", ".join(implementation_spec.core_features)
        )
    if implementation_spec.content_distribution:
        preserve_constraints.append(
            "content_distribution="
            + ", ".join(
                f"{content_type}:{count}"
                for content_type, count in implementation_spec.content_distribution.items()
            )
        )
    if input_intake_result and input_intake_result.runtime_config is not None:
        preserve_constraints.append(
            "runtime_content_output_filename="
            + input_intake_result.runtime_config.content_output_filename
        )

    must_fix: list[str] = []
    if target_agent == TARGET_SPEC:
        must_fix = [
            "service_summary를 구현 가능한 수준으로 더 구체화하라.",
            "normalized_requirements를 비워 두지 말고 downstream agent가 바로 쓸 수 있게 정리하라.",
            "delivery_expectations와 acceptance_focus를 실제 산출물 기준으로 명확히 하라.",
        ]
    elif target_agent == TARGET_REQUIREMENT:
        must_fix = [
            "implementation_targets를 실제 구현 작업 단위로 명확히 쓰라.",
            "app_constraints에 required screen/state/result/feedback 흐름 단서를 더 명확히 적어라.",
            "file_plan과 test_strategy가 downstream execution path를 충분히 설명하게 하라.",
        ]
    elif target_agent == TARGET_CONTENT:
        must_fix = [
            "interaction_units의 next_step과 feedback/result 흐름을 더 명확히 하라.",
            "evaluation_rules에 결과 요약과 완료 조건을 더 명확히 넣어라.",
            "Builder가 바로 화면 흐름으로 읽을 수 있게 interaction_units metadata를 보강하라.",
        ]

    if issue_type == "APP_GENERATION_FEEDBACK":
        if target_agent == TARGET_REQUIREMENT:
            must_fix.append("app_constraints에 state marker와 required result screen 조건을 명시하라.")
        elif target_agent == TARGET_CONTENT:
            must_fix.append("interaction_units에 result screen transition과 score summary 단계를 명시하라.")
        elif target_agent == TARGET_SPEC:
            must_fix.append("서비스 요약과 acceptance focus에 화면 흐름 기대치를 더 명확히 적어라.")

    return RetryInstruction(
        summary=f"{target_agent} 재실행 전, upstream contract를 더 명확히 보강해야 한다.",
        must_fix=_dedupe_preserve_order(must_fix),
        evidence=_dedupe_preserve_order(signals.evidence),
        preserve_constraints=_dedupe_preserve_order(preserve_constraints),
    )


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _has_upstream_alignment_issue(qa_issues: list[str]) -> bool:
    if not qa_issues:
        return False
    issue_text = " ".join(qa_issues).lower()
    upstream_markers = [
        "interaction",
        "semantic",
        "distribution",
        "configured content type",
        "learning_dimension",
        "missing from content output",
        "content output",
        "expected ",
    ]
    return any(marker in issue_text for marker in upstream_markers)
