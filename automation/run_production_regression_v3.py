from pathlib import Path
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
AUTOMATION = ROOT / "automation"

BASELINE_TESTS = [
    "test_publication_eligibility_v3.py",
    "test_publication_eligibility_adversarial_v3.py",
    "test_publication_orchestration_v3.py",
    "test_publication_runtime_adversarial_v3.py",
    "test_production_orchestration_contract_v3.py",
    "test_production_orchestration_execution_v3.py",
    "test_metrics_loader_orchestration_v3.py",
    "test_signal_orchestration_v3.py",
    "test_risk_orchestration_v3.py",
    "test_score_orchestration_v3.py",
    "test_score_runtime_adversarial_v3.py",
    "test_confidence_clock_v3.py",
    "test_b2k_e2e_v3.py",
]


def main():
    print("=" * 72)
    print("RADAR INSTITUCIONAL V3 - PRODUCTION REGRESSION")
    print("=" * 72)
    print(f"Python: {sys.executable}")
    print(f"Repository: {ROOT}")
    print(f"Baseline tests: {len(BASELINE_TESTS)}")
    print()

    results = []
    started_at = time.monotonic()

    for index, test_name in enumerate(BASELINE_TESTS, start=1):
        test_path = AUTOMATION / test_name

        print("=" * 72)
        print(f"[{index:02d}/{len(BASELINE_TESTS):02d}] {test_name}")
        print("=" * 72)

        if not test_path.is_file():
            print(f"[FAIL] Missing test: {test_path}")
            results.append(
                {
                    "test": test_name,
                    "returncode": 1,
                    "duration": 0.0,
                    "reason": "MISSING_TEST",
                }
            )
            print()
            continue

        test_started_at = time.monotonic()

        try:
            completed = subprocess.run(
                [sys.executable, str(test_path)],
                cwd=str(ROOT),
                check=False,
            )
            returncode = completed.returncode
            reason = "PASS" if returncode == 0 else "NONZERO_EXIT"

        except Exception as exc:
            returncode = 1
            reason = f"RUNNER_EXCEPTION: {type(exc).__name__}: {exc}"
            print(f"[FAIL] {reason}")

        duration = time.monotonic() - test_started_at

        results.append(
            {
                "test": test_name,
                "returncode": returncode,
                "duration": duration,
                "reason": reason,
            }
        )

        print()
        print(
            f"[{'PASS' if returncode == 0 else 'FAIL'}] "
            f"{test_name} "
            f"(exit={returncode}, {duration:.2f}s)"
        )
        print()

    total_duration = time.monotonic() - started_at
    failures = [item for item in results if item["returncode"] != 0]

    print("=" * 72)
    print("PRODUCTION REGRESSION SUMMARY")
    print("=" * 72)

    for item in results:
        status = "PASS" if item["returncode"] == 0 else "FAIL"
        print(
            f"[{status}] {item['test']} "
            f"(exit={item['returncode']}, "
            f"{item['duration']:.2f}s)"
        )

    print()
    print(f"Tests executed: {len(results)}")
    print(f"Failures: {len(failures)}")
    print(f"Duration: {total_duration:.2f}s")

    if failures:
        print("RESULT: FAILED")
        return 1

    print("RESULT: APPROVED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
