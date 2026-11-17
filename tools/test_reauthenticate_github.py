import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("reauthenticate_github.sh")

FAKE_GH = """#!/usr/bin/env bash
set -eu
printf '%s\\n' "$*" >> "$CALLS"
case "$1 $2" in
    "auth switch")
        if [[ "$SCENARIO" == missing && ! -f "$SIGNED_IN" ]]; then exit 1; fi
        ;;
    "auth login")
        if [[ "$SCENARIO" == cancelled ]]; then exit 1; fi
        touch "$SIGNED_IN"
        ;;
    "api --hostname")
        if [[ "$4" == user ]]; then
            if [[ "$SCENARIO" == expired && ! -f "$SIGNED_IN" ]]; then
                printf 'HTTP 401\\n' >&2
                exit 1
            fi
            if [[ "$SCENARIO" == wrong ]]; then
                printf 'another-account\\n'
            else
                printf 'vishnu4573\\n'
            fi
        elif [[ "$SCENARIO" == readonly ]]; then
            printf 'false\\n'
        else
            printf 'true\\n'
        fi
        ;;
    *) printf 'Unexpected gh invocation\\n' >&2; exit 2 ;;
esac
"""


class ReauthenticationTests(unittest.TestCase):
    def run_helper(self, *args, scenario="healthy", override=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gh = root / "gh"
            gh.write_text(FAKE_GH)
            gh.chmod(0o755)
            calls = root / "calls"
            env = os.environ.copy()
            env.pop("GH_TOKEN", None)
            env.pop("GITHUB_TOKEN", None)
            env.update(
                PATH=f"{root}:{env['PATH']}",
                CALLS=str(calls),
                SIGNED_IN=str(root / "signed-in"),
                SCENARIO=scenario,
            )
            if override:
                env["GH_TOKEN"] = "test-token-must-not-be-printed"
            result = subprocess.run(
                ["bash", str(SCRIPT), *args],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            return result, calls.read_text() if calls.exists() else ""

    def test_selects_healthy_account_without_login(self):
        result, calls = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("auth switch", calls)
        self.assertNotIn("auth login", calls)

    def test_expired_credentials_trigger_login_and_reverification(self):
        result, calls = self.run_helper(scenario="expired")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("auth login --hostname github.com --web", calls)
        self.assertEqual(calls.count("api --hostname github.com user"), 2)

    def test_check_does_not_change_authentication(self):
        result, calls = self.run_helper("--check", scenario="wrong")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Expected account", result.stderr)
        self.assertNotIn("auth ", calls)

    def test_missing_stored_account_triggers_signin(self):
        result, calls = self.run_helper(scenario="missing")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("auth login", calls)
        self.assertEqual(calls.count("auth switch"), 2)

    def test_wrong_browser_account_is_rejected(self):
        result, _ = self.run_helper("--reauth", scenario="wrong")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Expected account", result.stderr)

    def test_readonly_account_is_not_reported_as_success(self):
        result, _ = self.run_helper("--reauth", scenario="readonly")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not have repository write access", result.stderr)

    def test_environment_token_blocks_without_disclosing_token(self):
        result, calls = self.run_helper(override=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, "")
        self.assertNotIn("test-token-must-not-be-printed", result.stdout + result.stderr)

    def test_cancelled_login_stops_before_api_check(self):
        result, calls = self.run_helper("--reauth", scenario="cancelled")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("failed or was cancelled", result.stderr)
        self.assertNotIn("api ", calls)


if __name__ == "__main__":
    unittest.main()
