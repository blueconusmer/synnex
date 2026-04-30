from __future__ import annotations

from typing import Any

from pydantic import Field

from schemas.implementation.common import AgentLabel, InteractionUnit, QuizItem, SchemaModel
from schemas.implementation.implementation_spec import ImplementationSpec
from schemas.implementation.orchestration_decision import RetryInstruction
from schemas.implementation.requirement_mapping import RequirementMappingOutput
from schemas.implementation.spec_intake import SpecIntakeOutput


class ContentInteractionInput(SchemaModel):
    spec_intake_output: SpecIntakeOutput = Field(
        description="Normalized service spec from the intake stage."
    )
    requirement_mapping_output: RequirementMappingOutput = Field(
        description="Implementation contract from the requirement mapping stage."
    )
    implementation_spec: ImplementationSpec | None = Field(
        default=None,
        description="Runtime implementation configuration passed through the pipeline.",
    )
    retry_instruction: RetryInstruction | None = Field(
        default=None,
        description="Optional feedback-loop retry instruction for revising content and interaction output.",
    )


class SemanticValidationItemResult(SchemaModel):
    item_id: str = Field(description="Validated quiz item id.")
    current_quiz_type: str = Field(description="Quiz type before any local relabeling.")
    expected_quiz_type: str = Field(description="Quiz type inferred from the item action.")
    quiz_type_match: bool = Field(description="Whether the current quiz type matched the inferred action.")
    current_learning_dimension: str = Field(
        description="Learning dimension before any local relabeling."
    )
    expected_learning_dimension: str = Field(
        description="Learning dimension inferred from the item meaning."
    )
    learning_dimension_match: bool = Field(
        description="Whether the current learning dimension matched the inferred meaning."
    )
    applied_label_corrections: list[str] = Field(
        default_factory=list,
        description="Local relabeling actions that were applied to the item.",
    )
    requires_regeneration: bool = Field(
        default=False,
        description="Whether the item had to be regenerated after validation.",
    )
    reasons: list[str] = Field(
        default_factory=list,
        description="Reasons produced by the semantic validator.",
    )


class SemanticValidationSummary(SchemaModel):
    total_items: int = Field(description="Total number of quiz items after validation.")
    quiz_type_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Final quiz-type distribution after validation.",
    )
    learning_dimension_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Final learning-dimension distribution after validation.",
    )
    learning_dimension_values_valid: bool = Field(
        description="Whether every learning dimension used an allowed value."
    )
    quiz_type_distribution_valid: bool = Field(
        description="Whether the generated quiz types matched the configured content types."
    )
    semantic_validator_passed: bool = Field(
        description="Whether all items passed the semantic validator after repair."
    )
    regeneration_requested: bool = Field(
        description="Whether any item was regenerated during validation."
    )
    regeneration_count: int = Field(description="Number of regenerated items.")
    regenerated_item_ids: list[str] = Field(
        default_factory=list,
        description="Item ids that were regenerated once during validation.",
    )
    item_results: list[SemanticValidationItemResult] = Field(
        default_factory=list,
        description="Per-item semantic validation outcomes.",
    )


class InteractionValidationSummary(SchemaModel):
    interaction_mode: str = Field(description="Interaction strategy hint used by the agent.")
    mode_inference_reason: str = Field(
        default="",
        description="Deterministic explanation for how interaction_mode was inferred.",
    )
    unit_count: int = Field(description="Total number of interaction units.")
    unit_type_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Counts by interaction_type.",
    )
    structure_valid: bool = Field(
        description="Whether interaction_units satisfied the structural validator.",
    )
    issues: list[str] = Field(
        default_factory=list,
        description="Validation issues found in the interaction-unit structure.",
    )


class ContentInteractionOutput(SchemaModel):
    agent: AgentLabel | None = Field(default=None, description="Agent label metadata.")
    service_summary: str = Field(
        description="Short summary describing the generated educational service."
    )
    interaction_mode: str = Field(
        default="quiz",
        description="Generation and validation hint: quiz, coaching, or general.",
    )
    interaction_mode_reason: str = Field(
        default="",
        description="Reason why the interaction_mode was chosen.",
    )
    quiz_types: list[str] = Field(
        default_factory=list,
        description="Distinct quiz types represented in the generated content.",
    )
    items: list[QuizItem] = Field(
        default_factory=list,
        description="Generated quiz items for the current MVP.",
    )
    answer_key: dict[str, str] = Field(
        default_factory=dict,
        description="Answer key keyed by item id.",
    )
    explanations: dict[str, str] = Field(
        default_factory=dict,
        description="Explanation text keyed by item id.",
    )
    learning_points: dict[str, str] = Field(
        default_factory=dict,
        description="Learning point text keyed by item id.",
    )
    interaction_notes: list[str] = Field(
        default_factory=list,
        description="Notes describing how the learner should experience the quiz flow.",
    )
    interaction_units: list[InteractionUnit] = Field(
        default_factory=list,
        description="Primary structured interaction flow units for downstream builders.",
    )
    flow_notes: list[str] = Field(
        default_factory=list,
        description="High-level flow notes describing how the interaction should progress.",
    )
    evaluation_rules: dict[str, Any] = Field(
        default_factory=dict,
        description="Generalized evaluation rules for quiz scoring or coaching feedback.",
    )
    semantic_validation: SemanticValidationSummary | None = Field(
        default=None,
        description="Semantic validation summary for the generated content.",
    )
    interaction_validation: InteractionValidationSummary | None = Field(
        default=None,
        description="Structural validation summary for interaction_units.",
    )
