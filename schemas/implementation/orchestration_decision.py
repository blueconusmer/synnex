from __future__ import annotations

from typing import Literal

from pydantic import Field

from schemas.implementation.common import SchemaModel


OverallStatus = Literal[
    "PASS",
    "RETRY_COMPLETED",
    "RETRY_RECOMMENDED",
    "NEEDS_HUMAN_REVIEW",
    "OUT_OF_SCOPE",
]
IssueType = Literal[
    "NONE",
    "SPEC_INTERPRETATION_ISSUE",
    "REQUIREMENT_MAPPING_ISSUE",
    "CONTENT_INTERACTION_ISSUE",
    "APP_GENERATION_FEEDBACK",
    "AMBIGUOUS_ISSUE",
]
ObservedStage = Literal["prototype_builder", "run_test_and_fix", "qa_alignment", "none"]
TargetAgent = Literal[
    "SPEC_INTAKE",
    "REQUIREMENT_MAPPING",
    "CONTENT_INTERACTION",
    "NONE",
    "HUMAN_REVIEW",
]


class RetryInstruction(SchemaModel):
    summary: str = Field(
        default="",
        description="Short retry summary for the selected upstream agent.",
    )
    must_fix: list[str] = Field(
        default_factory=list,
        description="Concrete problems the retried agent must address.",
    )
    evidence: list[str] = Field(
        default_factory=list,
        description="Observed evidence that triggered the retry decision.",
    )
    preserve_constraints: list[str] = Field(
        default_factory=list,
        description="Constraints that must be preserved during revision.",
    )


class RetryHistoryEntry(SchemaModel):
    cycle_index: int = Field(description="1-based retry cycle index.")
    issue_type: IssueType = Field(description="Issue type observed for this cycle.")
    target_agent: TargetAgent = Field(description="Agent targeted for this retry cycle.")
    llm_judge_used: bool = Field(
        default=False,
        description="Whether the ambiguous-case LLM judge was used.",
    )
    instruction_summary: str = Field(
        default="",
        description="Short retry instruction summary for this cycle.",
    )
    result_status: str = Field(
        default="",
        description="Outcome observed after this retry cycle finished.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Additional notes about the cycle result.",
    )


class OrchestrationJudgeOutput(SchemaModel):
    chosen_target_agent: Literal[
        "SPEC_INTAKE",
        "REQUIREMENT_MAPPING",
        "CONTENT_INTERACTION",
        "HUMAN_REVIEW",
    ] = Field(description="Chosen upstream agent or human review target.")
    reason: str = Field(description="Why the chosen target agent is the best retry target.")
    retry_instruction: RetryInstruction = Field(
        description="Retry instruction to send to the selected target agent."
    )
    confidence_note: str = Field(
        default="",
        description="Short note about ambiguity or confidence.",
    )


class OrchestrationDecision(SchemaModel):
    overall_status: OverallStatus = Field(description="Final orchestration decision status.")
    issue_type: IssueType = Field(description="Detected issue type.")
    observed_stage: ObservedStage = Field(description="Stage where the main signal was observed.")
    target_agent: TargetAgent = Field(description="Selected retry target or terminal target.")
    candidate_agents: list[TargetAgent] = Field(
        default_factory=list,
        description="Candidate target agents considered during routing.",
    )
    reason: str = Field(description="Why this decision was made.")
    recommended_action: str = Field(description="Short recommended next action.")
    retry_required: bool = Field(description="Whether an upstream retry should be executed.")
    retry_instruction: RetryInstruction = Field(
        default_factory=RetryInstruction,
        description="Structured retry instruction for the target agent.",
    )
    llm_judge_used: bool = Field(
        default=False,
        description="Whether the LLM judge was used for ambiguous routing.",
    )
    llm_judge_status: str = Field(
        default="NOT_USED",
        description="Judge status such as NOT_USED, SUCCESS, FAILED, or INVALID_OUTPUT.",
    )
    retry_count: int = Field(
        default=0,
        description="Number of retries already executed before this decision.",
    )
    max_retry_count: int = Field(
        default=3,
        description="Maximum upstream retry count allowed for this loop.",
    )
    should_stop: bool = Field(description="Whether the feedback loop should stop now.")
    stop_reason: str = Field(
        default="",
        description="Why the loop should stop, if applicable.",
    )
