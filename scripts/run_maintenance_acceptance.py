#!/usr/bin/env python3
"""Isolated maintenance exercise; see docs/spec.md section 13."""
from __future__ import annotations

import argparse
from pathlib import Path

from learning_exercise import LearningExercise
from run_acceptance import DEFAULT_EVIDENCE_ROOT, AcceptanceError


class MaintenanceRun(LearningExercise):
    def workflow(self) -> None:
        raise AcceptanceError("maintenance behavioral stages are not implemented")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--check-environment", action="store_true")
    args = parser.parse_args()
    try:
        run = MaintenanceRun(args.run_id, DEFAULT_EVIDENCE_ROOT / args.run_id)
        run.run((lambda: None) if args.check_environment else run.workflow, required=set(), complete=not args.check_environment)
    except (AcceptanceError, OSError) as error:
        print(f"Maintenance failed: {error}")
        return 1
    print("Maintenance environment CHECKPOINT" if args.check_environment else "Maintenance PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
