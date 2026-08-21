"""Thin subprocess wrapper around the Azure CLI (`az`) and `az rest`.

The suite deliberately avoids any Azure SDK dependency: every Azure interaction
goes through the installed `az` CLI via :class:`AzClient`. Each call is logged
to a per-session log file under ``reports/`` and returns a structured
:class:`AzResult`.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union


@dataclass
class AzResult:
    """Structured result of a single `az` invocation."""

    success: bool
    stdout: str
    stderr: str
    returncode: int
    data: Optional[Union[dict, list]]
    duration_seconds: float
    command: str = ""
    dry_run: bool = False

    def as_evidence(self) -> Dict[str, Any]:
        """Return a JSON-serialisable summary suitable for a TestResult evidence dict."""
        return {
            "command": self.command,
            "success": self.success,
            "returncode": self.returncode,
            "duration_seconds": round(self.duration_seconds, 3),
            "stdout_excerpt": (self.stdout or "")[:2000],
            "stderr_excerpt": (self.stderr or "")[:2000],
            "dry_run": self.dry_run,
        }


class AzClient:
    """Runs `az` CLI commands as subprocesses with logging and dry-run support."""

    def __init__(
        self,
        timeout_seconds: int = 300,
        dry_run: bool = False,
        log_dir: str = "reports",
        session_id: Optional[str] = None,
    ) -> None:
        """Create a client.

        Args:
            timeout_seconds: Default per-command timeout.
            dry_run: If True, commands are logged and a synthetic success result
                is returned without executing anything.
            log_dir: Directory for the session log file.
            session_id: Optional explicit session id; a timestamp is used otherwise.
        """
        self.timeout_seconds = timeout_seconds
        self.dry_run = dry_run
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)
        ts = session_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.session_log = os.path.join(self.log_dir, f"session_{ts}.log")
        self._current_test_id: str = "-"
        self._log(f"=== AzClient session started (dry_run={dry_run}) ===")

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    def set_current_test(self, poc_id: str) -> None:
        """Tag subsequent log lines with the currently-executing test id."""
        self._current_test_id = poc_id or "-"

    def _log(self, message: str) -> None:
        stamp = datetime.now(timezone.utc).isoformat()
        line = f"[{stamp}] [{self._current_test_id}] {message}\n"
        try:
            with open(self.session_log, "a", encoding="utf-8") as fh:
                fh.write(line)
        except OSError:
            pass  # Logging must never break a test run.

    # ------------------------------------------------------------------
    # Core execution
    # ------------------------------------------------------------------
    def run(
        self,
        args: List[str],
        parse_json: bool = True,
        timeout: Optional[int] = None,
        capture_stderr_verbose: bool = False,
    ) -> AzResult:
        """Run ``az <args>`` and return an :class:`AzResult`.

        Args:
            args: Argument list WITHOUT the leading ``az`` (e.g. ``["vm", "show", ...]``).
            parse_json: If True, attempt to parse stdout as JSON into ``data``.
            timeout: Override the default timeout for this call.
            capture_stderr_verbose: If True, ensure ``--verbose`` is present so
                rate-limit headers are emitted to stderr (used by throttle tests).
        """
        full_args = ["az"] + list(args)
        if capture_stderr_verbose and "--verbose" not in full_args:
            full_args.append("--verbose")
        command_str = " ".join(shlex.quote(a) for a in full_args)
        effective_timeout = timeout or self.timeout_seconds

        if self.dry_run:
            self._log(f"DRY-RUN command: {command_str}")
            return AzResult(
                success=True,
                stdout="",
                stderr="",
                returncode=0,
                data=None,
                duration_seconds=0.0,
                command=command_str,
                dry_run=True,
            )

        self._log(f"RUN command: {command_str}")
        start = time.time()
        try:
            proc = subprocess.run(
                full_args,
                capture_output=True,
                text=True,
                timeout=effective_timeout,
            )
            duration = time.time() - start
            stdout, stderr, rc = proc.stdout, proc.stderr, proc.returncode
        except subprocess.TimeoutExpired as exc:
            duration = time.time() - start
            stdout = exc.stdout or "" if isinstance(exc.stdout, str) else ""
            stderr = (exc.stderr or "" if isinstance(exc.stderr, str) else "") + \
                f"\n[TIMEOUT after {effective_timeout}s]"
            rc = 124
            self._log(f"TIMEOUT after {effective_timeout}s: {command_str}")
        except FileNotFoundError:
            duration = time.time() - start
            stdout, stderr, rc = "", "az CLI not found on PATH", 127
            self._log("ERROR: az CLI not found on PATH")

        data: Optional[Union[dict, list]] = None
        if parse_json and stdout.strip():
            try:
                data = json.loads(stdout)
            except json.JSONDecodeError:
                data = None

        success = rc == 0
        self._log(
            f"RESULT rc={rc} duration={duration:.2f}s "
            f"stdout_len={len(stdout)} stderr_len={len(stderr)}"
        )
        if stdout:
            self._log(f"STDOUT: {stdout[:4000]}")
        if stderr:
            self._log(f"STDERR: {stderr[:4000]}")

        return AzResult(
            success=success,
            stdout=stdout,
            stderr=stderr,
            returncode=rc,
            data=data,
            duration_seconds=duration,
            command=command_str,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def set_subscription(self, subscription_id: str) -> AzResult:
        """Set the active subscription for subsequent commands."""
        return self.run(
            ["account", "set", "--subscription", subscription_id],
            parse_json=False,
        )

    def az_rest(
        self,
        method: str,
        url: str,
        body: Optional[Union[dict, list]] = None,
        query: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
    ) -> AzResult:
        """Run an ``az rest`` call.

        Args:
            method: HTTP method (GET, POST, PUT, PATCH, DELETE).
            url: Full ARM URL including api-version query string.
            body: Optional JSON body — serialised and passed via ``--body``.
            query: Optional JMESPath ``--query`` filter.
            headers: Optional additional headers passed as ``--headers k=v``.
            timeout: Optional timeout override.
        """
        args = ["rest", "--method", method.upper(), "--url", url]
        if body is not None:
            args += ["--body", json.dumps(body)]
            # ARM PATCH/PUT/POST bodies are JSON.
            args += ["--headers", "Content-Type=application/json"]
        if headers:
            for key, value in headers.items():
                args += ["--headers", f"{key}={value}"]
        if query:
            args += ["--query", query]
        return self.run(args, parse_json=True, timeout=timeout)

    def graph_query(
        self,
        kusto: str,
        subscription_id: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> AzResult:
        """Run an Azure Resource Graph query via ``az graph query``.

        Requires the ``resource-graph`` CLI extension; if it is missing az will
        prompt to install it (non-interactive runs will surface the error).
        """
        args = ["graph", "query", "-q", kusto, "--output", "json"]
        if subscription_id:
            args += ["--subscriptions", subscription_id]
        return self.run(args, parse_json=True, timeout=timeout)
