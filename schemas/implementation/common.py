from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SchemaModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AgentLabel(SchemaModel):
    english_name: str = Field(description="English agent name used in code or APIs.")
    korean_name: str = Field(description="Human-friendly Korean agent name.")


class QuizGenerationRequirements(SchemaModel):
    quiz_type_count: int = Field(description="Number of quiz types to generate.")
    items_per_type: int = Field(description="Number of items for each quiz type.")
    total_items: int = Field(description="Total item count across all quiz types.")
    required_fields: list[str] = Field(
        default_factory=list,
        description="Required fields on every generated quiz item.",
    )


class QuizItem(SchemaModel):
    item_id: str = Field(description="Unique quiz item identifier.")
    quiz_type: str = Field(description="Quiz type or category for the item.")
    difficulty: str = Field(
        default="",
        description="Optional difficulty level such as intro or main.",
    )
    learning_dimension: str = Field(
        description="Question-power dimension targeted by the quiz item."
    )
    title: str = Field(description="Short display title for the item.")
    topic_context: str = Field(
        default="",
        description="Optional topic or learning context shown with the item.",
    )
    situation: str = Field(
        default="",
        description="Optional situation-card prompt or scenario shown to the learner.",
    )
    original_question: str = Field(
        default="",
        description="Optional original learner question used by Quest-style flows.",
    )
    stage_level: str = Field(
        default="",
        description="Optional stage or league level used by battle-style quest flows.",
    )
    question: str = Field(description="Question text shown to the learner.")
    choices: list[str] = Field(
        default_factory=list,
        description="Optional multiple-choice options for selection-based quiz items.",
    )
    correct_choice: str = Field(
        default="",
        description="Correct answer string from the choices when the item is selection-based.",
    )
    explanation: str = Field(description="Why the correct choice is correct.")
    learning_point: str = Field(description="Educational takeaway from the item.")
    ai_question: str = Field(
        default="",
        description="Optional pre-authored AI rival question used by battle-style quest flows.",
    )


class InteractionUnit(SchemaModel):
    unit_id: str = Field(description="Unique interaction-unit identifier.")
    interaction_type: str = Field(
        description="Interaction type such as multiple_choice, free_text_input, feedback, or coaching_feedback."
    )
    title: str = Field(default="", description="Optional short title for the unit.")
    learner_action: str = Field(
        default="",
        description="What the learner is expected to do at this step.",
    )
    system_response: str = Field(
        default="",
        description="What the system shows or says during this step.",
    )
    input_format: str = Field(
        default="",
        description="Optional input format hint, for example multiple choice or free text.",
    )
    feedback_rule: str = Field(
        default="",
        description="Rule or policy describing how feedback is produced at this step.",
    )
    learning_dimension: str = Field(
        default="",
        description="Learning dimension associated with this interaction step, if any.",
    )
    next_step: str = Field(
        default="",
        description="Next unit id or END when the interaction flow finishes.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional structured metadata used by downstream builders.",
    )


class GeneratedFile(SchemaModel):
    path: str = Field(description="Relative file path to create or update.")
    description: str = Field(description="Why this generated file exists.")
    content: str = Field(description="Full file contents.")


class LocalCheckResult(SchemaModel):
    check_name: str = Field(description="Name of the local validation check.")
    command: str = Field(description="Command or operation that was executed.")
    passed: bool = Field(description="Whether the check passed.")
    details: str = Field(default="", description="Human-readable details for the check.")


class FailureRecord(SchemaModel):
    check_name: str = Field(description="Check that failed.")
    summary: str = Field(description="Short failure summary.")
    details: str = Field(description="Detailed failure context.")


class PatchedFile(SchemaModel):
    path: str = Field(description="Relative file path to patch.")
    reason: str = Field(description="Why this patch is proposed or applied.")
    content: str = Field(description="Patched file content.")
