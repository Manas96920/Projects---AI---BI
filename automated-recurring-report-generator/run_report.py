"""Unattended entry point; uses exactly the same functions as the notebook."""
import argparse
import sys
from datetime import date
from pathlib import Path

from report_pipeline import ReportConfig, run_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a recurring Olist PDF report")
    parser.add_argument("--frequency", choices=["weekly", "monthly"], default="monthly")
    parser.add_argument("--mode", choices=["historical", "calendar"], default="historical")
    parser.add_argument("--as-of", type=date.fromisoformat, help="Anchor date YYYY-MM-DD; report the previous completed period")
    parser.add_argument("--ai", choices=["auto", "off", "required"], default="auto")
    parser.add_argument("--model", default="gemini-3.5-flash-lite")
    parser.add_argument("--env-file", type=Path)
    args = parser.parse_args()
    cfg = ReportConfig(frequency=args.frequency, mode=args.mode, as_of=args.as_of,
                       ai_mode=args.ai, model=args.model, env_file=args.env_file)
    try:
        result = run_pipeline(cfg)
    except Exception as exc:
        # Never emit raw driver/API messages; they can contain connection details.
        print(f"Report failed ({type(exc).__name__}). Check .env, database schema and logs/report_pipeline.log.", file=sys.stderr)
        return 1
    print("PDF:", result["pdf_path"])
    print("Summary source:", result["summary"]["source"])
    if result["summary"].get("fallback_reason"):
        print("Fallback:", result["summary"]["fallback_reason"])
    print("Manifest:", result["run_dir"] / "manifest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
