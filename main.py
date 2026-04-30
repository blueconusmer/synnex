from __future__ import annotations

import argparse
import json
from pathlib import Path

from clients.env import load_env_file
from clients.llm import FallbackLLMClient
from loaders import load_input_intake
from orchestrator.pipeline import ImplementationPipeline
from schemas.planning_package import ValidationStatus


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the education-service implementation team pipeline."
    )
    parser.add_argument(
        "--input-path",
        default="inputs/quiz_service_spec.md",
        help="Path to the source Markdown implementation spec.",
    )
    parser.add_argument(
        "--input-package",
        default=None,
        help="Path to a six-file planning package directory.",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs",
        help="Directory where pipeline outputs should be written.",
    )
    parser.add_argument(
        "--app-path",
        default="app.py",
        help="Path where the generated Streamlit app should be written.",
    )
    parser.add_argument(
        "--skip-streamlit-smoke",
        action="store_true",
        help="Skip the Streamlit smoke test after generating the app.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    load_env_file(Path(".env"))
    input_path = Path(args.input_path)
    implementation_spec = None
    input_intake_result = None
    if args.input_package:
        input_path = Path(args.input_package)
        input_intake_result = load_input_intake(input_path)
        if input_intake_result.status == ValidationStatus.FAIL:
            _write_input_intake_report(Path(args.output_dir), input_intake_result)
            print("[FAILED] Input Intake Layer")
            for issue in input_intake_result.issues:
                print(f"- {issue.code}: {issue.message}")
            return 1
        if input_intake_result.status == ValidationStatus.NEEDS_PLANNING_REVIEW:
            _write_input_intake_report(Path(args.output_dir), input_intake_result)
            print(
                "[WARNING] Input Intake Layer requires planning review; "
                "continuing under warn-and-continue policy."
            )
            print(
                f"- planning_review_items: {len(input_intake_result.planning_review_items)}"
            )
            for item in input_intake_result.planning_review_items:
                print(f"- REVIEW {item.field_path}: {item.reason}")
        implementation_spec = input_intake_result.implementation_spec
    llm_client = FallbackLLMClient.from_env()
    pipeline = ImplementationPipeline(
        llm_client=llm_client,
        spec_path=input_path,
        workspace_dir=Path.cwd(),
        output_dir=Path(args.output_dir),
        implementation_spec=implementation_spec,
        input_intake_result=input_intake_result,
        app_target_path=Path(args.app_path),
        enable_streamlit_smoke=not args.skip_streamlit_smoke,
    )
    pipeline.run()
    return 0


def _write_input_intake_report(output_dir: Path, input_intake_result) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "input_intake_report.json").write_text(
        json.dumps(input_intake_result.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
