"""Unit tests for the Model Router CLI (Phase X).

All subprocess calls are mocked — no real Ollama is invoked.
Tests cover:
  - Config loading from models.yaml
  - Dispatch to implementation_model (mocked subprocess)
  - Log file creation and content
  - Fallback chain when primary model fails
  - Hard rejection when Claude is configured as implementation_model
  - ModelUnavailableError when all models fail
  - CLI (scripts/route_task.py) argument parsing and exit codes
  - Claude is never used as a fallback
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest
import yaml

from src.router.config_loader import ModelEntry, RouterConfig, RouterConfigError, load_router_config
from src.router.dispatch import (
    ClaudeRouteAttemptError,
    ModelUnavailableError,
    dispatch,
)
from src.router.model_router import ModelRouter
from src.router.router_log import RouterLogEntry, make_entry, write_log_entry

_MODELS_YAML = Path(__file__).parents[2] / "config" / "models.yaml"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_config(
    provider: str = "ollama-cloud",
    model: str = "glm-5.2:cloud",
    command: str = "ollama run glm-5.2:cloud",
    fallbacks: list[dict] | None = None,
) -> RouterConfig:
    return RouterConfig(
        implementation_model=ModelEntry(
            provider=provider,
            model=model,
            command=command,
        ),
        architecture_model_provider="claude",
        fallback_order=[
            ModelEntry(
                provider=fb["provider"],
                model=fb["model"],
                command=fb["command"],
            )
            for fb in (fallbacks or [])
        ],
        timeout_seconds=30,
        max_retries=1,
    )


def _mock_run_ok(stdout: str = "mock output") -> MagicMock:
    result = MagicMock()
    result.returncode = 0
    result.stdout = stdout
    result.stderr = ""
    return result


def _mock_run_fail(returncode: int = 1, stderr: str = "command not found") -> MagicMock:
    result = MagicMock()
    result.returncode = returncode
    result.stdout = ""
    result.stderr = stderr
    return result


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

class TestConfigLoading:
    def test_loads_real_models_yaml(self):
        config = load_router_config(_MODELS_YAML)
        assert config.implementation_model.provider == "ollama-cloud"

    def test_implementation_model_has_command(self):
        config = load_router_config(_MODELS_YAML)
        assert config.implementation_model.command != ""

    def test_implementation_model_is_not_claude(self):
        config = load_router_config(_MODELS_YAML)
        assert config.implementation_model.provider != "claude"

    def test_architecture_model_is_claude(self):
        config = load_router_config(_MODELS_YAML)
        assert config.architecture_model_provider == "claude"

    def test_fallback_order_populated(self):
        config = load_router_config(_MODELS_YAML)
        assert len(config.fallback_order) >= 1

    def test_timeout_seconds_loaded(self):
        config = load_router_config(_MODELS_YAML)
        assert config.timeout_seconds > 0

    def test_missing_file_raises_config_error(self, tmp_path):
        with pytest.raises(RouterConfigError, match="not found"):
            load_router_config(tmp_path / "nonexistent.yaml")

    def test_missing_implementation_model_section_raises(self, tmp_path):
        cfg = tmp_path / "models.yaml"
        cfg.write_text(yaml.dump({"version": 1}))
        with pytest.raises(RouterConfigError, match="implementation_model"):
            load_router_config(cfg)

    def test_missing_provider_field_raises(self, tmp_path):
        cfg = tmp_path / "models.yaml"
        cfg.write_text(yaml.dump({
            "implementation_model": {"model": "glm", "command": "ollama run glm"},
        }))
        with pytest.raises(RouterConfigError, match="provider"):
            load_router_config(cfg)

    def test_missing_model_field_raises(self, tmp_path):
        cfg = tmp_path / "models.yaml"
        cfg.write_text(yaml.dump({
            "implementation_model": {"provider": "ollama-cloud", "command": "ollama run glm"},
        }))
        with pytest.raises(RouterConfigError, match="model"):
            load_router_config(cfg)

    def test_missing_command_field_raises(self, tmp_path):
        cfg = tmp_path / "models.yaml"
        cfg.write_text(yaml.dump({
            "implementation_model": {"provider": "ollama-cloud", "model": "glm"},
        }))
        with pytest.raises(RouterConfigError, match="command"):
            load_router_config(cfg)

    def test_signin_command_loaded(self):
        config = load_router_config(_MODELS_YAML)
        assert config.implementation_model.signin_command is not None

    def test_invalid_yaml_raises_config_error(self, tmp_path):
        cfg = tmp_path / "models.yaml"
        cfg.write_text(": invalid: yaml: [[[")
        with pytest.raises(Exception):
            load_router_config(cfg)


# ---------------------------------------------------------------------------
# Dispatch — success paths
# ---------------------------------------------------------------------------

class TestDispatchSuccess:
    def test_dispatches_to_implementation_model(self, tmp_path):
        config = _minimal_config()
        with patch("subprocess.run", return_value=_mock_run_ok("hello")) as mock_run:
            output = dispatch("test_task", "write some code", config, log_dir=tmp_path)
        assert output == "hello"
        mock_run.assert_called_once()

    def test_prompt_sent_via_stdin(self, tmp_path):
        config = _minimal_config()
        with patch("subprocess.run", return_value=_mock_run_ok()) as mock_run:
            dispatch("test_task", "my prompt", config, log_dir=tmp_path)
        _, kwargs = mock_run.call_args
        assert kwargs["input"] == "my prompt"

    def test_command_is_split_and_executed(self, tmp_path):
        config = _minimal_config(command="ollama run glm-5.2:cloud")
        with patch("subprocess.run", return_value=_mock_run_ok()) as mock_run:
            dispatch("test_task", "prompt", config, log_dir=tmp_path)
        args, _ = mock_run.call_args
        assert args[0] == ["ollama", "run", "glm-5.2:cloud"]

    def test_output_returned_to_caller(self, tmp_path):
        config = _minimal_config()
        with patch("subprocess.run", return_value=_mock_run_ok("generated code here")):
            output = dispatch("test_task", "prompt", config, log_dir=tmp_path)
        assert output == "generated code here"

    def test_timeout_passed_to_subprocess(self, tmp_path):
        config = _minimal_config()
        config = RouterConfig(
            implementation_model=config.implementation_model,
            architecture_model_provider="claude",
            fallback_order=[],
            timeout_seconds=42,
        )
        with patch("subprocess.run", return_value=_mock_run_ok()) as mock_run:
            dispatch("test_task", "prompt", config, log_dir=tmp_path)
        _, kwargs = mock_run.call_args
        assert kwargs["timeout"] == 42


# ---------------------------------------------------------------------------
# Dispatch — failure and fallback
# ---------------------------------------------------------------------------

class TestDispatchFailureAndFallback:
    def test_raises_model_unavailable_when_all_fail(self, tmp_path):
        config = _minimal_config()
        with patch("subprocess.run", side_effect=FileNotFoundError("ollama not found")):
            with pytest.raises(ModelUnavailableError):
                dispatch("test_task", "prompt", config, log_dir=tmp_path)

    def test_error_message_does_not_mention_claude_fallback(self, tmp_path):
        config = _minimal_config()
        with patch("subprocess.run", side_effect=FileNotFoundError("not found")):
            with pytest.raises(ModelUnavailableError, match="does not fall back to Claude"):
                dispatch("test_task", "prompt", config, log_dir=tmp_path)

    def test_tries_fallback_when_primary_fails(self, tmp_path):
        config = _minimal_config(
            fallbacks=[{
                "provider": "local-ollama",
                "model": "qwen3:14b",
                "command": "ollama run qwen3:14b",
            }]
        )
        primary_fail = _mock_run_fail()
        fallback_ok = _mock_run_ok("fallback output")

        with patch("subprocess.run", side_effect=[subprocess.SubprocessError("fail"), fallback_ok]):
            output = dispatch("test_task", "prompt", config, log_dir=tmp_path)

        assert output == "fallback output"

    def test_skips_claude_in_fallback_chain(self, tmp_path):
        """If a fallback entry happens to use Claude provider, it is skipped silently."""
        config = _minimal_config(
            fallbacks=[
                {"provider": "claude", "model": "opus", "command": "claude run"},
                {"provider": "local-ollama", "model": "qwen3:14b", "command": "ollama run qwen3:14b"},
            ]
        )
        primary_fail = subprocess.SubprocessError("primary fail")
        local_ok = _mock_run_ok("local fallback output")

        calls = [primary_fail, local_ok]
        with patch("subprocess.run", side_effect=calls):
            output = dispatch("test_task", "prompt", config, log_dir=tmp_path)

        assert output == "local fallback output"

    def test_timeout_error_triggers_fallback(self, tmp_path):
        config = _minimal_config(
            fallbacks=[{
                "provider": "local-ollama",
                "model": "qwen3:14b",
                "command": "ollama run qwen3:14b",
            }]
        )
        with patch("subprocess.run", side_effect=[
            subprocess.TimeoutExpired("ollama", 30),
            _mock_run_ok("recovered"),
        ]):
            output = dispatch("test_task", "prompt", config, log_dir=tmp_path)

        assert output == "recovered"

    def test_raises_when_all_fallbacks_exhausted(self, tmp_path):
        config = _minimal_config(
            fallbacks=[{
                "provider": "local-ollama",
                "model": "qwen3:14b",
                "command": "ollama run qwen3:14b",
            }]
        )
        with patch("subprocess.run", side_effect=FileNotFoundError("not found")):
            with pytest.raises(ModelUnavailableError):
                dispatch("test_task", "prompt", config, log_dir=tmp_path)

    def test_nonzero_exit_code_raises_subprocess_error(self, tmp_path):
        config = _minimal_config()
        with patch("subprocess.run", return_value=_mock_run_fail(returncode=127)):
            with pytest.raises(ModelUnavailableError):
                dispatch("test_task", "prompt", config, log_dir=tmp_path)


# ---------------------------------------------------------------------------
# Claude guard
# ---------------------------------------------------------------------------

class TestClaudeGuard:
    def test_claude_provider_raises_immediately(self, tmp_path):
        config = _minimal_config(provider="claude", model="opus", command="claude run")
        with pytest.raises(ClaudeRouteAttemptError):
            dispatch("test_task", "prompt", config, log_dir=tmp_path)

    def test_anthropic_provider_raises_immediately(self, tmp_path):
        config = _minimal_config(provider="anthropic", model="claude-3", command="claude run")
        with pytest.raises(ClaudeRouteAttemptError):
            dispatch("test_task", "prompt", config, log_dir=tmp_path)

    def test_claude_guard_message_mentions_config(self, tmp_path):
        config = _minimal_config(provider="claude", model="opus", command="claude run")
        with pytest.raises(ClaudeRouteAttemptError, match="models.yaml"):
            dispatch("test_task", "prompt", config, log_dir=tmp_path)

    def test_claude_guard_does_not_call_subprocess(self, tmp_path):
        config = _minimal_config(provider="claude", model="opus", command="claude run")
        with patch("subprocess.run") as mock_run:
            with pytest.raises(ClaudeRouteAttemptError):
                dispatch("test_task", "prompt", config, log_dir=tmp_path)
        mock_run.assert_not_called()

    def test_real_config_does_not_raise_claude_guard(self, tmp_path):
        config = load_router_config(_MODELS_YAML)
        with patch("subprocess.run", return_value=_mock_run_ok("output")):
            output = dispatch("test_task", "prompt", config, log_dir=tmp_path)
        assert output == "output"


# ---------------------------------------------------------------------------
# Log file
# ---------------------------------------------------------------------------

class TestLogFile:
    def test_log_file_created_on_success(self, tmp_path):
        config = _minimal_config()
        with patch("subprocess.run", return_value=_mock_run_ok("out")):
            dispatch("my_task", "prompt", config, log_dir=tmp_path)
        assert (tmp_path / "router_log.jsonl").exists()

    def test_log_entry_records_task_name(self, tmp_path):
        config = _minimal_config()
        with patch("subprocess.run", return_value=_mock_run_ok("out")):
            dispatch("my_unique_task", "prompt", config, log_dir=tmp_path)
        lines = (tmp_path / "router_log.jsonl").read_text().strip().splitlines()
        entry = json.loads(lines[-1])
        assert entry["task_name"] == "my_unique_task"

    def test_log_entry_records_provider(self, tmp_path):
        config = _minimal_config(provider="ollama-cloud")
        with patch("subprocess.run", return_value=_mock_run_ok()):
            dispatch("task", "prompt", config, log_dir=tmp_path)
        entry = json.loads((tmp_path / "router_log.jsonl").read_text().strip().splitlines()[-1])
        assert entry["provider"] == "ollama-cloud"

    def test_log_entry_records_model(self, tmp_path):
        config = _minimal_config(model="glm-5.2:cloud")
        with patch("subprocess.run", return_value=_mock_run_ok()):
            dispatch("task", "prompt", config, log_dir=tmp_path)
        entry = json.loads((tmp_path / "router_log.jsonl").read_text().strip().splitlines()[-1])
        assert entry["model"] == "glm-5.2:cloud"

    def test_log_entry_records_command(self, tmp_path):
        config = _minimal_config(command="ollama run glm-5.2:cloud")
        with patch("subprocess.run", return_value=_mock_run_ok()):
            dispatch("task", "prompt", config, log_dir=tmp_path)
        entry = json.loads((tmp_path / "router_log.jsonl").read_text().strip().splitlines()[-1])
        assert entry["command"] == "ollama run glm-5.2:cloud"

    def test_log_entry_success_true_on_success(self, tmp_path):
        config = _minimal_config()
        with patch("subprocess.run", return_value=_mock_run_ok()):
            dispatch("task", "prompt", config, log_dir=tmp_path)
        entry = json.loads((tmp_path / "router_log.jsonl").read_text().strip().splitlines()[-1])
        assert entry["success"] is True

    def test_log_entry_success_false_on_failure(self, tmp_path):
        config = _minimal_config()
        with patch("subprocess.run", side_effect=FileNotFoundError("not found")):
            with pytest.raises(ModelUnavailableError):
                dispatch("task", "prompt", config, log_dir=tmp_path)
        entry = json.loads((tmp_path / "router_log.jsonl").read_text().strip().splitlines()[-1])
        assert entry["success"] is False

    def test_log_entry_records_timestamp(self, tmp_path):
        config = _minimal_config()
        with patch("subprocess.run", return_value=_mock_run_ok()):
            dispatch("task", "prompt", config, log_dir=tmp_path)
        entry = json.loads((tmp_path / "router_log.jsonl").read_text().strip().splitlines()[-1])
        assert entry["timestamp"] > 0

    def test_log_entry_records_output_length(self, tmp_path):
        config = _minimal_config()
        with patch("subprocess.run", return_value=_mock_run_ok("hello world")):
            dispatch("task", "prompt", config, log_dir=tmp_path)
        entry = json.loads((tmp_path / "router_log.jsonl").read_text().strip().splitlines()[-1])
        assert entry["output_length"] == len("hello world")

    def test_log_entry_fallback_used_true_when_fallback_used(self, tmp_path):
        config = _minimal_config(
            fallbacks=[{
                "provider": "local-ollama",
                "model": "qwen3:14b",
                "command": "ollama run qwen3:14b",
            }]
        )
        with patch("subprocess.run", side_effect=[
            subprocess.SubprocessError("primary fail"),
            _mock_run_ok("fallback ok"),
        ]):
            dispatch("task", "prompt", config, log_dir=tmp_path)
        entry = json.loads((tmp_path / "router_log.jsonl").read_text().strip().splitlines()[-1])
        assert entry["fallback_used"] is True

    def test_log_entry_fallback_used_false_when_primary_succeeds(self, tmp_path):
        config = _minimal_config()
        with patch("subprocess.run", return_value=_mock_run_ok()):
            dispatch("task", "prompt", config, log_dir=tmp_path)
        entry = json.loads((tmp_path / "router_log.jsonl").read_text().strip().splitlines()[-1])
        assert entry["fallback_used"] is False

    def test_log_appends_across_multiple_calls(self, tmp_path):
        config = _minimal_config()
        with patch("subprocess.run", return_value=_mock_run_ok()):
            dispatch("task_a", "prompt", config, log_dir=tmp_path)
            dispatch("task_b", "prompt", config, log_dir=tmp_path)
        lines = (tmp_path / "router_log.jsonl").read_text().strip().splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["task_name"] == "task_a"
        assert json.loads(lines[1])["task_name"] == "task_b"

    def test_log_entry_error_field_set_on_failure(self, tmp_path):
        config = _minimal_config()
        with patch("subprocess.run", side_effect=FileNotFoundError("ollama not found")):
            with pytest.raises(ModelUnavailableError):
                dispatch("task", "prompt", config, log_dir=tmp_path)
        entry = json.loads((tmp_path / "router_log.jsonl").read_text().strip().splitlines()[-1])
        assert entry["error"] is not None

    def test_log_lines_are_valid_json(self, tmp_path):
        config = _minimal_config()
        with patch("subprocess.run", return_value=_mock_run_ok("out")):
            dispatch("task", "prompt", config, log_dir=tmp_path)
        for line in (tmp_path / "router_log.jsonl").read_text().strip().splitlines():
            json.loads(line)


# ---------------------------------------------------------------------------
# RouterLogEntry / write_log_entry
# ---------------------------------------------------------------------------

class TestRouterLogEntry:
    def test_write_log_entry_creates_file(self, tmp_path):
        entry = make_entry(
            task_name="t", provider="p", model="m", command="c",
            success=True,
        )
        path = write_log_entry(entry, log_dir=tmp_path)
        assert path.exists()

    def test_log_entry_fields_round_trip(self, tmp_path):
        entry = make_entry(
            task_name="my_task",
            provider="ollama-cloud",
            model="glm-5.2:cloud",
            command="ollama run glm-5.2:cloud",
            success=True,
            output_length=42,
        )
        path = write_log_entry(entry, log_dir=tmp_path)
        d = json.loads(path.read_text().strip())
        assert d["task_name"] == "my_task"
        assert d["provider"] == "ollama-cloud"
        assert d["model"] == "glm-5.2:cloud"
        assert d["success"] is True
        assert d["output_length"] == 42

    def test_make_entry_timestamp_is_recent(self):
        import time
        before = time.time()
        entry = make_entry(task_name="t", provider="p", model="m", command="c", success=True)
        after = time.time()
        assert before <= entry.timestamp <= after


# ---------------------------------------------------------------------------
# ModelRouter public API
# ---------------------------------------------------------------------------

class TestModelRouter:
    def test_router_exposes_implementation_model(self):
        config = _minimal_config()
        router = ModelRouter(config=config)
        assert router.implementation_model == "glm-5.2:cloud"

    def test_router_exposes_provider(self):
        config = _minimal_config()
        router = ModelRouter(config=config)
        assert router.implementation_provider == "ollama-cloud"

    def test_router_exposes_command(self):
        config = _minimal_config()
        router = ModelRouter(config=config)
        assert router.implementation_command == "ollama run glm-5.2:cloud"

    def test_router_run_dispatches_and_returns_output(self, tmp_path):
        config = _minimal_config()
        router = ModelRouter(config=config, log_dir=tmp_path)
        with patch("subprocess.run", return_value=_mock_run_ok("result text")):
            output = router.run("my_task", "some prompt")
        assert output == "result text"

    def test_router_run_raises_model_unavailable_on_failure(self, tmp_path):
        config = _minimal_config()
        router = ModelRouter(config=config, log_dir=tmp_path)
        with patch("subprocess.run", side_effect=FileNotFoundError("not found")):
            with pytest.raises(ModelUnavailableError):
                router.run("my_task", "prompt")

    def test_router_loads_from_real_config(self, tmp_path):
        router = ModelRouter(config_path=_MODELS_YAML, log_dir=tmp_path)
        assert router.implementation_provider == "ollama-cloud"

    def test_router_never_uses_claude(self, tmp_path):
        config = _minimal_config()
        router = ModelRouter(config=config, log_dir=tmp_path)
        assert router.implementation_provider not in ("claude", "anthropic")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class TestCLI:
    def _run_cli(self, argv: list[str]) -> tuple[int, str, str]:
        import io
        from contextlib import redirect_stderr, redirect_stdout
        from scripts.route_task import main
        out = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_dry_run_exits_zero(self):
        code, out, _ = self._run_cli(["--task", "x", "--dry-run"])
        assert code == 0

    def test_dry_run_prints_implementation_model(self):
        _, out, _ = self._run_cli(["--task", "x", "--dry-run"])
        assert "implementation_model" in out

    def test_dry_run_prints_command(self):
        _, out, _ = self._run_cli(["--task", "x", "--dry-run"])
        assert "command" in out

    def test_missing_task_exits_nonzero(self):
        import sys
        with pytest.raises(SystemExit) as exc:
            self._run_cli(["--prompt", "foo"])
        assert exc.value.code != 0

    def test_success_exits_zero(self, tmp_path):
        with patch("subprocess.run", return_value=_mock_run_ok("done")):
            code, out, _ = self._run_cli([
                "--task", "test",
                "--prompt", "write code",
                "--log-dir", str(tmp_path),
            ])
        assert code == 0
        assert "done" in out

    def test_unavailable_model_exits_one(self, tmp_path):
        with patch("subprocess.run", side_effect=FileNotFoundError("not found")):
            code, _, err = self._run_cli([
                "--task", "test",
                "--prompt", "write code",
                "--log-dir", str(tmp_path),
            ])
        assert code == 1
        assert "ERROR" in err

    def test_missing_prompt_file_exits_two(self, tmp_path):
        code, _, err = self._run_cli([
            "--task", "test",
            "--prompt-file", str(tmp_path / "nonexistent.txt"),
        ])
        assert code == 2

    def test_prompt_file_is_sent_to_model(self, tmp_path):
        prompt_file = tmp_path / "task.txt"
        prompt_file.write_text("build the feature")
        with patch("subprocess.run", return_value=_mock_run_ok("built")) as mock_run:
            code, _, _ = self._run_cli([
                "--task", "impl",
                "--prompt-file", str(prompt_file),
                "--log-dir", str(tmp_path),
            ])
        assert code == 0
        _, kwargs = mock_run.call_args
        assert kwargs["input"] == "build the feature"

    def test_claude_route_blocked_exits_three(self, tmp_path):
        bad_yaml = tmp_path / "models.yaml"
        bad_yaml.write_text(yaml.dump({
            "defaults": {"timeout_seconds": 30, "max_retries": 1},
            "implementation_model": {
                "provider": "claude",
                "model": "opus",
                "command": "claude run",
            },
        }))
        with patch("subprocess.run", return_value=_mock_run_ok()):
            code, _, err = self._run_cli([
                "--task", "test",
                "--prompt", "do stuff",
                "--config", str(bad_yaml),
                "--log-dir", str(tmp_path),
            ])
        assert code == 3
        assert "ERROR" in err

    def test_missing_config_file_exits_two(self, tmp_path):
        code, _, err = self._run_cli([
            "--task", "test",
            "--prompt", "p",
            "--config", str(tmp_path / "missing.yaml"),
        ])
        assert code == 2
