from __future__ import annotations

from pydantic import Field

from schemas.common import ProjectBrief, SchemaModel


class ProductPlannerInput(SchemaModel):
    project_brief: ProjectBrief = Field(
        description="Starting brief grounded in docs/project_context.md."
    )


class ProductPlannerOutput(SchemaModel):
    problem_definition: str = Field(description="Problem the team is solving in the current stage.")
    project_goal: str = Field(description="Concrete goal for the current project stage.")
    target_user: str = Field(description="Primary target user for the service concept.")
    mvp_scope: list[str] = Field(
        default_factory=list,
        description="Minimum scope that the team should deliver in the current stage.",
    )
    excluded_scope: list[str] = Field(
        default_factory=list,
        description="Out-of-scope items for the current stage.",
    )
    user_flow: list[str] = Field(
        default_factory=list,
        description="High-level flow that later agents should build on.",
    )
