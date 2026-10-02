from pathlib import Path
import ast
import sys

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "automation" / "run_production_regression_v3.py"

EXPECTED_TESTS = [
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

passed = 0
failed = 0


def check(condition, description):
    global passed, failed

    if condition:
        passed += 1
        print(f"[PASS] {description}")
    else:
        failed += 1
        print(f"[FAIL] {description}")


print("=" * 72)
print("B.2L.7B - PERMANENT PRODUCTION REGRESSION CONTRACT")
print("=" * 72)

check(RUNNER.exists(), "Permanent production regression runner exists.")

if RUNNER.exists():
    source = RUNNER.read_text(encoding="utf-8-sig")
    tree = ast.parse(source)

    check(
        "subprocess" in source,
        "Runner uses subprocess isolation.",
    )

    check(
        "sys.executable" in source,
        "Runner uses the active Python interpreter.",
    )

    for test_name in EXPECTED_TESTS:
        check(
            test_name in source,
            f"Baseline includes {test_name}.",
        )

    check(
        "Tests executed:" in source,
        "Runner reports executed test count.",
    )

    check(
        "Failures:" in source,
        "Runner reports failure count.",
    )

    check(
        "RESULT:" in source,
        "Runner reports final result.",
    )

    check(
        "return 0" in source or "SystemExit(0)" in source,
        "Runner exposes success exit code.",
    )

    check(
        "return 1" in source or "SystemExit(1)" in source,
        "Runner exposes failure exit code.",
    )

    subprocess_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "subprocess"
    ]

    check(
        len(subprocess_calls) > 0,
        "Runner contains subprocess execution calls.",
    )

print()
print("=" * 72)
print("RESULT")
print("=" * 72)
print(f"PASS: {passed}")
print(f"FAIL: {failed}")

if failed:
    print(
        "RESULT: EXPECTED RED UNTIL PERMANENT "
        "PRODUCTION REGRESSION RUNNER IS IMPLEMENTED"
    )
    raise SystemExit(1)

print("RESULT: PERMANENT PRODUCTION REGRESSION CONTRACT APPROVED")
raise SystemExit(0)
