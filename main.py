from __future__ import annotations

import argparse
from pathlib import Path

from clients.env import load_env_file
from clients.llm import OpenAICompatibleClient
from loaders import load_planning_package, planning_package_to_implementation_spec
from orchestrator.pipeline import ImplementationPipeline


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
        help="Path to a six-file planning package directory that will be adapted into the pipeline input schema.",
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
    llm_client = OpenAICompatibleClient.from_env()

    implementation_spec = None
    spec_path = Path(args.input_path)
    if args.input_package:
        package_dir = Path(args.input_package)
        package = load_planning_package(package_dir)
        implementation_spec = planning_package_to_implementation_spec(package, package_dir)
        spec_path = package_dir

    pipeline = ImplementationPipeline(
        llm_client=llm_client,
        spec_path=spec_path,
        workspace_dir=Path.cwd(),
        output_dir=Path(args.output_dir),
        implementation_spec=implementation_spec,
        app_target_path=Path(args.app_path),
        enable_streamlit_smoke=not args.skip_streamlit_smoke,
    )
    pipeline.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
