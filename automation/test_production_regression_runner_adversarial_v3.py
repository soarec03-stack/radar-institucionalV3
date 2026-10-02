from pathlib import Path
import contextlib
import importlib.util
import io
import tempfile


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "automation" / "run_production_regression_v3.py"

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


def load_runner():
    spec = importlib.util.spec_from_file_location(
        "production_regression_runner_under_test",
        RUNNER_PATH,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load production regression runner.")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_main(module):
    buffer = io.StringIO()

    with contextlib.redirect_stdout(buffer):
        returncode = module.main()

    return returncode, buffer.getvalue()


print("=" * 72)
print("B.2L.7E - PRODUCTION REGRESSION RUNNER ADVERSARIAL")
print("=" * 72)

check(
    RUNNER_PATH.is_file(),
    "Permanent production regression runner exists.",
)

if RUNNER_PATH.is_file():
    with tempfile.TemporaryDirectory(
        prefix="radar_v3_regression_runner_"
    ) as temp_dir:
        temp_path = Path(temp_dir)

        passing_test = temp_path / "synthetic_pass.py"
        failing_test = temp_path / "synthetic_fail.py"

        passing_test.write_text(
            "raise SystemExit(0)\n",
            encoding="utf-8",
        )

        failing_test.write_text(
            "raise SystemExit(7)\n",
            encoding="utf-8",
        )

        # ------------------------------------------------------------
        # CASE A - ALL PASS
        # ------------------------------------------------------------
        runner_pass = load_runner()
        runner_pass.AUTOMATION = temp_path
        runner_pass.BASELINE_TESTS = [
            passing_test.name,
        ]

        pass_code, pass_output = run_main(runner_pass)

        check(
            pass_code == 0,
            "All-pass synthetic baseline returns exit code 0.",
        )

        check(
            "Tests executed: 1" in pass_output,
            "All-pass run reports exactly one executed test.",
        )

        check(
            "Failures: 0" in pass_output,
            "All-pass run reports zero failures.",
        )

        check(
            "RESULT: APPROVED" in pass_output,
            "All-pass run reports APPROVED.",
        )

        # ------------------------------------------------------------
        # CASE B - ONE PASS + ONE FAIL
        # ------------------------------------------------------------
        runner_fail = load_runner()
        runner_fail.AUTOMATION = temp_path
        runner_fail.BASELINE_TESTS = [
            passing_test.name,
            failing_test.name,
        ]

        fail_code, fail_output = run_main(runner_fail)

        check(
            fail_code == 1,
            "Synthetic failing baseline propagates exit code 1.",
        )

        check(
            "Tests executed: 2" in fail_output,
            "Failing run continues and reports both tests.",
        )

        check(
            "Failures: 1" in fail_output,
            "Failing run reports exactly one failure.",
        )

        check(
            "RESULT: FAILED" in fail_output,
            "Failing run reports FAILED.",
        )

        check(
            "[FAIL] synthetic_fail.py" in fail_output,
            "Failing test is identified in summary.",
        )

        # ------------------------------------------------------------
        # CASE C - MISSING TEST
        # ------------------------------------------------------------
        runner_missing = load_runner()
        runner_missing.AUTOMATION = temp_path
        runner_missing.BASELINE_TESTS = [
            "synthetic_missing.py",
        ]

        missing_code, missing_output = run_main(runner_missing)

        check(
            missing_code == 1,
            "Missing baseline test fails closed.",
        )

        check(
            "Tests executed: 1" in missing_output,
            "Missing-test run records attempted test.",
        )

        check(
            "Failures: 1" in missing_output,
            "Missing-test run records one failure.",
        )

        check(
            "RESULT: FAILED" in missing_output,
            "Missing-test run reports FAILED.",
        )

print()
print("=" * 72)
print("RESULT")
print("=" * 72)
print(f"PASS: {passed}")
print(f"FAIL: {failed}")

if failed:
    print("RESULT: PRODUCTION REGRESSION RUNNER ADVERSARIAL FAILED")
    raise SystemExit(1)

print("RESULT: PRODUCTION REGRESSION RUNNER ADVERSARIAL APPROVED")
raise SystemExit(0)
