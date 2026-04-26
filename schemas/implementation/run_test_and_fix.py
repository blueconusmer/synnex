from __future__ import annotations

from pydantic import Field

from schemas.implementation.common import (
    AgentLabel,
    FailureRecord,
    LocalCheckResult,
    PatchedFile,
    SchemaModel,
)
from schemas.implementation.prototype_builder import PrototypeBuilderOutput


class RunTestAndFixInput(SchemaModel):
    prototype_builder_output: PrototypeBuilderOutput = Field(
        description="Generated code artifacts from the builder stage."
    )
    check_results: list[LocalCheckResult] = Field(
        default_factory=list,
        description="Local compile and smoke-test results.",
    )


class RunTestAndFixOutput(SchemaModel):
    agent: AgentLabel | None = Field(default=None, description="Agent label metadata.")
    checks_run: list[str] = Field(
        default_factory=list, description="Checks that were executed."
    )
    failures: list[FailureRecord] = Field(
        default_factory=list, description="Failures observed during execution."
    )
    fixes_applied: list[str] = Field(
        default_factory=list, description="Fixes applied or proposed."
    )
    remaining_risks: list[str] = Field(
        default_factory=list, description="Remaining issues after the test/fix stage."
    )
    patched_files: list[PatchedFile] = Field(
        default_factory=list, description="Patched files to materialize if needed."
    )
    should_retry_builder: bool = Field(
        default=False,
        description="Whether the orchestrator should run another local check pass.",
    )
