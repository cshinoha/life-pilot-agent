"""LLM CLI runner — subprocess execution with retry."""

import json
import logging
import os
import re
import shutil
import signal
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, TypedDict

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 1200  # 20 minutes
CODEX_DEVICE_LOGIN_URL = "https://auth.openai.com/codex/device"
CODEX_DEVICE_CODE_TTL_SECONDS = 15 * 60
CODEX_BOOTSTRAP_WAIT_SECONDS = 6.0

_ERROR_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"file.+not found", re.IGNORECASE), "Skill data unavailable"),
    (re.compile(r"permission denied", re.IGNORECASE), "System error"),
    (re.compile(r"mcp", re.IGNORECASE), "Task integration unavailable"),
    (
        re.compile(r"connection (refused|reset|timed out)", re.IGNORECASE),
        "Service connection error",
    ),
    (re.compile(r"ENOENT|EACCES|EPERM", re.IGNORECASE), "System error"),
    (re.compile(r"traceback|stacktrace", re.IGNORECASE), "Internal processing error"),
]
_ANSI_ESCAPE_PATTERN = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
_CODEX_AUTH_FAILURE_PATTERN = re.compile(
    r"401\s+Unauthorized|Missing bearer|not logged in|authentication",
    re.IGNORECASE,
)


def _sanitize_error(raw: str) -> str:
    """Replace raw error details with user-friendly messages.

    Full error is already logged before this function is called.
    """
    for pattern, friendly in _ERROR_PATTERNS:
        if pattern.search(raw):
            return friendly
    if len(raw) > 150 or "/" in raw:
        return "Processing error"
    return raw


class RuntimeStatus(TypedDict):
    """Readiness status for the selected LLM runtime."""

    ready: bool
    summary: str
    details: str


class PendingCodexAuth(TypedDict):
    """Persisted state for an in-flight Codex device login."""

    code: str
    login_url: str
    log_path: str
    started_at: float
    expires_at: float
    pid: int


class ClaudeRunner:
    """Runs LLM CLI (Codex or Claude) as a subprocess."""

    def __init__(
        self, vault_path: Path,
        timeout: int = DEFAULT_TIMEOUT,
        llm_cli: str = "codex",
        default_model: str = "",
    ) -> None:
        self.vault_path = Path(vault_path).resolve()
        self.timeout = timeout
        self.llm_cli = llm_cli.strip().lower() or "codex"
        self.default_model = default_model.strip()
        self._mcp_config_path = (
            self.vault_path.parent / "mcp-config.json"
        ).resolve()

    @property
    def _project_root(self) -> Path:
        return self.vault_path.parent

    @property
    def _codex_auth_state_path(self) -> Path:
        return self._project_root / ".codex-device-auth.json"

    @property
    def _codex_auth_log_path(self) -> Path:
        return self._project_root / ".codex-device-auth.log"

    def run(
        self, prompt: str, label: str, model: str = "",
    ) -> dict[str, Any]:
        """Run Claude CLI with one retry on non-zero exit (not on timeout).

        Args:
            prompt: The prompt to send to Claude.
            label: Human-readable label for log messages.

        Returns:
            Dict with "report" on success or "error" on failure.
        """
        runtime_status = self.get_runtime_status(trigger_bootstrap=True)
        if not runtime_status["ready"]:
            return {
                "error": runtime_status["details"] or runtime_status["summary"],
                "processed_entries": 0,
            }

        effective_model = model or self.default_model
        result = self._execute(prompt, label, model=effective_model)
        if "error" in result and "timed out" not in result["error"]:
            logger.info("Retrying %s after failure...", label)
            time.sleep(3)
            result = self._execute(prompt, label, model=effective_model)
        return result

    def get_runtime_status(self, trigger_bootstrap: bool = False) -> RuntimeStatus:
        """Return readiness status for the configured runtime."""
        if self.llm_cli != "codex":
            return {
                "ready": True,
                "summary": f"{self.llm_cli} готов",
                "details": "",
            }

        if not shutil.which("codex"):
            return {
                "ready": False,
                "summary": "Codex CLI не найден",
                "details": "Codex CLI не установлен на сервере.",
            }

        if self._codex_is_logged_in():
            self._clear_pending_codex_auth()
            return {
                "ready": True,
                "summary": "Codex авторизован",
                "details": "",
            }

        pending_auth = self._load_pending_codex_auth()
        if pending_auth:
            return {
                "ready": False,
                "summary": "Codex ждёт авторизацию",
                "details": self._format_pending_codex_auth(pending_auth),
            }

        if not trigger_bootstrap:
            return {
                "ready": False,
                "summary": "Codex не авторизован",
                "details": (
                    "Codex CLI не авторизован. Следующий LLM-запрос "
                    "автоматически запустит device auth bootstrap."
                ),
            }

        pending_auth = self._start_codex_device_auth()
        if pending_auth:
            return {
                "ready": False,
                "summary": "Codex ждёт авторизацию",
                "details": self._format_pending_codex_auth(pending_auth),
            }

        return {
            "ready": False,
            "summary": "Codex bootstrap не стартовал",
            "details": (
                "Не удалось подготовить device auth для Codex. "
                "Проверь `codex login --device-auth` на сервере."
            ),
        }

    def _build_command(
        self, prompt: str, model: str, output_path: str,
    ) -> list[str]:
        """Build subprocess command for selected LLM CLI."""
        if self.llm_cli == "claude":
            cmd = [
                "claude",
                "--print",
                "--dangerously-skip-permissions",
                "--mcp-config",
                str(self._mcp_config_path),
            ]
            if model:
                cmd.extend(["--model", model])
            cmd.extend(["-p", prompt])
            return cmd

        # Default: codex exec with browser-auth-backed local session
        cmd = [
            "codex",
            "exec",
            "--skip-git-repo-check",
            "--dangerously-bypass-approvals-and-sandbox",
            "--output-last-message",
            output_path,
        ]
        if model:
            cmd.extend(["--model", model])
        cmd.append(prompt)
        return cmd

    def _codex_is_logged_in(self) -> bool:
        """Check whether the local Codex CLI already has credentials."""
        try:
            proc = subprocess.run(
                ["codex", "login", "status"],
                cwd=self._project_root,
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
                env=os.environ.copy(),
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

        output = f"{proc.stdout}\n{proc.stderr}".lower()
        if "not logged in" in output or "logged out" in output:
            return False
        return proc.returncode == 0

    def _load_pending_codex_auth(self) -> PendingCodexAuth | None:
        """Load an existing device-auth bootstrap if it is still usable."""
        state_path = self._codex_auth_state_path
        if not state_path.exists():
            return None

        try:
            raw_state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("Could not read pending Codex auth state")
            self._clear_pending_codex_auth()
            return None

        pending_auth = self._coerce_pending_codex_auth(raw_state)
        if not pending_auth:
            self._clear_pending_codex_auth()
            return None

        if pending_auth["expires_at"] <= time.time():
            self._cleanup_pending_codex_auth(pending_auth)
            return None

        if not self._is_pid_running(pending_auth["pid"]):
            self._clear_pending_codex_auth()
            return None

        return pending_auth

    def _coerce_pending_codex_auth(
        self, raw_state: object,
    ) -> PendingCodexAuth | None:
        """Validate persisted auth state loaded from JSON."""
        if not isinstance(raw_state, dict):
            return None

        code = raw_state.get("code")
        login_url = raw_state.get("login_url")
        log_path = raw_state.get("log_path")
        started_at = raw_state.get("started_at")
        expires_at = raw_state.get("expires_at")
        pid = raw_state.get("pid")

        if not isinstance(code, str) or not code:
            return None
        if not isinstance(login_url, str) or not login_url:
            return None
        if not isinstance(log_path, str) or not log_path:
            return None
        if not isinstance(started_at, (int, float)):
            return None
        if not isinstance(expires_at, (int, float)):
            return None
        if not isinstance(pid, int):
            return None

        return {
            "code": code,
            "login_url": login_url,
            "log_path": log_path,
            "started_at": float(started_at),
            "expires_at": float(expires_at),
            "pid": pid,
        }

    def _start_codex_device_auth(self) -> PendingCodexAuth | None:
        """Launch Codex device-auth in background and capture the device code."""
        pending_auth = self._load_pending_codex_auth()
        if pending_auth:
            return pending_auth

        log_path = self._codex_auth_log_path
        log_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with log_path.open("w", encoding="utf-8") as log_file:
                proc = subprocess.Popen(
                    ["codex", "login", "--device-auth"],
                    cwd=self._project_root,
                    stdin=subprocess.DEVNULL,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    text=True,
                    env=os.environ.copy(),
                    start_new_session=True,
                )
        except FileNotFoundError:
            logger.error("Codex CLI not found while starting device auth")
            return None
        except OSError:
            logger.exception("Failed to start Codex device auth")
            return None

        code = ""
        login_url = CODEX_DEVICE_LOGIN_URL
        deadline = time.monotonic() + CODEX_BOOTSTRAP_WAIT_SECONDS

        while time.monotonic() < deadline:
            auth_log = self._read_auth_log(log_path)
            login_url, code = self._extract_device_auth_data(auth_log)
            if code:
                break
            if proc.poll() is not None:
                break
            time.sleep(0.25)

        if not code:
            auth_log = self._read_auth_log(log_path)
            logger.error(
                "Codex device auth did not yield a code. Output: %.400s",
                auth_log,
            )
            if proc.poll() is None:
                self._terminate_pid(proc.pid)
            return None

        pending_auth = {
            "code": code,
            "login_url": login_url,
            "log_path": str(log_path),
            "started_at": time.time(),
            "expires_at": time.time() + CODEX_DEVICE_CODE_TTL_SECONDS,
            "pid": proc.pid,
        }
        self._save_pending_codex_auth(pending_auth)
        return pending_auth

    def _save_pending_codex_auth(self, pending_auth: PendingCodexAuth) -> None:
        """Persist the current bootstrap state for reuse across requests."""
        try:
            self._codex_auth_state_path.write_text(
                json.dumps(pending_auth, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            logger.exception("Failed to persist Codex auth state")

    def _clear_pending_codex_auth(self) -> None:
        """Delete any persisted bootstrap metadata and stale log files."""
        for path in (self._codex_auth_state_path, self._codex_auth_log_path):
            try:
                if path.exists():
                    path.unlink()
            except OSError:
                logger.warning("Could not remove %s", path)

    def _cleanup_pending_codex_auth(
        self, pending_auth: PendingCodexAuth,
    ) -> None:
        """Stop an expired bootstrap process and remove local state."""
        self._terminate_pid(pending_auth["pid"])
        self._clear_pending_codex_auth()

    def _is_pid_running(self, pid: int) -> bool:
        """Check whether a background bootstrap process is still alive."""
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True

    def _terminate_pid(self, pid: int) -> None:
        """Terminate a stale background bootstrap process."""
        if not self._is_pid_running(pid):
            return
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            logger.warning("Could not terminate stale Codex auth PID %s", pid)

    def _read_auth_log(self, log_path: Path) -> str:
        """Read the current device-auth log file safely."""
        try:
            return log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""

    def _extract_device_auth_data(self, auth_log: str) -> tuple[str, str]:
        """Extract the login URL and one-time code from Codex output."""
        clean_log = _ANSI_ESCAPE_PATTERN.sub("", auth_log)
        url_match = re.search(r"https://auth\.openai\.com/codex/device", clean_log)
        code_match = re.search(r"[A-Z0-9]{4}-[A-Z0-9]{5}", clean_log)
        login_url = url_match.group(0) if url_match else CODEX_DEVICE_LOGIN_URL
        code = code_match.group(0) if code_match else ""
        return login_url, code

    def _format_pending_codex_auth(self, pending_auth: PendingCodexAuth) -> str:
        """Create a user-facing message for an in-flight device login."""
        expires_at = datetime.fromtimestamp(pending_auth["expires_at"])
        expires_text = expires_at.strftime("%H:%M")
        return (
            "Codex требует авторизации. Открой "
            f"{pending_auth['login_url']} и введи код {pending_auth['code']}.\n"
            "Bootstrap-процесс уже запущен на сервере — после подтверждения "
            "просто повтори команду.\n"
            f"Код действует примерно до {expires_text}."
        )

    def _execute(
        self, prompt: str, label: str, model: str = "",
    ) -> dict[str, Any]:
        """Single execution of selected LLM CLI."""
        output_path = ""
        try:
            env = os.environ.copy()

            output_file = tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False,
            )
            output_path = output_file.name
            output_file.close()

            cmd = self._build_command(prompt, model, output_path)

            proc = subprocess.run(
                cmd,
                cwd=self.vault_path.parent,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
                env=env,
            )

            output_text = ""
            try:
                with open(output_path, encoding="utf-8") as f:
                    output_text = f.read().strip()
            except OSError:
                output_text = ""

            logger.info(
                "%s rc=%s stdout=%.200s stderr=%.200s",
                label,
                proc.returncode,
                proc.stdout,
                proc.stderr,
            )

            if proc.returncode != 0:
                error_detail = (
                    proc.stderr.strip()
                    or proc.stdout.strip()[:200]
                    or f"exit code {proc.returncode}"
                )
                if (
                    self.llm_cli == "codex"
                    and _CODEX_AUTH_FAILURE_PATTERN.search(error_detail)
                ):
                    pending_auth = self._start_codex_device_auth()
                    if pending_auth:
                        return {
                            "error": self._format_pending_codex_auth(pending_auth),
                            "processed_entries": 0,
                        }
                logger.error(
                    "%s failed (rc=%s): %s",
                    label,
                    proc.returncode,
                    error_detail,
                )
                return {
                    "error": f"{label} failed: {_sanitize_error(error_detail)}",
                    "processed_entries": 0,
                }

            if not output_text:
                output_text = proc.stdout.strip()

            return {
                "report": output_text,
                "processed_entries": 1,
            }

        except subprocess.TimeoutExpired:
            logger.error("%s timed out", label)
            return {
                "error": f"{label} timed out",
                "processed_entries": 0,
            }
        except FileNotFoundError:
            logger.error("%s CLI not found", self.llm_cli)
            return {
                "error": f"{self.llm_cli} CLI not installed",
                "processed_entries": 0,
            }
        except Exception as e:
            logger.exception("Unexpected error during %s", label)
            return {"error": _sanitize_error(str(e)), "processed_entries": 0}
        finally:
            if output_path:
                try:
                    os.remove(output_path)
                except Exception:
                    pass

    def load_skill_content(self) -> str:
        """Load life-pilot-processor skill content."""
        skill_path = (
            self.vault_path / ".claude/skills/life-pilot-processor/SKILL.md"
        )
        if skill_path.exists():
            return skill_path.read_text()
        return ""

    def load_tasknotes_reference(self) -> str:
        """Load TaskNotes reference for inclusion in prompt."""
        ref_path = (
            self.vault_path
            / ".claude/skills/life-pilot-processor/references/tasknotes.md"
        )
        if ref_path.exists():
            return ref_path.read_text()
        return ""

    @staticmethod
    def truncate_for_telegram(
        text: str, limit: int = 4096
    ) -> str:
        """Truncate message to fit Telegram's character limit."""
        if len(text) <= limit:
            return text
        truncated = text[: limit - 40]
        last_nl = truncated.rfind("\n")
        if last_nl > limit // 2:
            truncated = truncated[:last_nl]
        return truncated + "\n\n... (обрезано, слишком длинное)"
