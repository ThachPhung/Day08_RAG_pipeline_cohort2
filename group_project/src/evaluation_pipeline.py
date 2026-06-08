"""Entry point for Viet's group evaluation work.

The official deliverable files stay in group_project/evaluation/:
    - golden_dataset.json
    - eval_pipeline.py
    - results.md

This wrapper lets the group source folder expose the same evaluation pipeline
without duplicating code.
"""

from __future__ import annotations

import runpy
from pathlib import Path


EVAL_PIPELINE_PATH = Path(__file__).resolve().parents[1] / "evaluation" / "eval_pipeline.py"


def main() -> None:
    """Run group_project/evaluation/eval_pipeline.py."""
    runpy.run_path(str(EVAL_PIPELINE_PATH), run_name="__main__")


if __name__ == "__main__":
    main()
