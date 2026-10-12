"""
metrics.py - Evaluation report metrics endpoint.
"""

import json
from pathlib import Path
from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/metrics", tags=["Metrics"])


@router.get(
    "/evaluation",
    summary="Retrieve stored test-set accuracy and evaluation report",
)
def get_evaluation_metrics():
    report_path = Path(__file__).resolve().parent.parent.parent / "reports" / "evaluation.json"
    if not report_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation report not found. Run 'python scripts/evaluate.py' to generate benchmark metrics.",
        )

    with open(report_path, "r", encoding="utf-8") as f:
        return json.load(f)
