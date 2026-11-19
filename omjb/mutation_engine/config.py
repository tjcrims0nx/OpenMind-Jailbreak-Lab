"""Non-secret endpoint configuration with CLI > file > environment precedence."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any


def _read_config(path: str | Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    source = Path(path)
    raw = source.read_text(encoding="utf-8")
    if source.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml
        except ImportError as exc:
            raise RuntimeError("YAML config requires: pip install 'openmind-omjb[yaml]'") from exc
        data = yaml.safe_load(raw)
    else:
        data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("endpoint config must be a JSON/YAML object")
    return data


def resolve_endpoint_config(*, cli_endpoint: str | None = None,
                            cli_timeout: float | None = None,
                            cli_token_env: str | None = None,
                            config_path: str | Path | None = None,
                            environ: dict[str, str] | None = None) -> dict[str, Any]:
    """Resolve endpoint settings. Secret values are read only from the environment."""
    env = os.environ if environ is None else environ
    file_config = _read_config(config_path)
    allowed = {"endpoint", "timeout", "token_env"}
    unknown = sorted(set(file_config) - allowed)
    if unknown:
        raise ValueError("unsupported config keys: " + ", ".join(unknown))

    endpoint = cli_endpoint if cli_endpoint is not None else file_config.get(
        "endpoint", env.get("OMJB_GUARDRAIL_ENDPOINT"))
    timeout = cli_timeout if cli_timeout is not None else file_config.get(
        "timeout", env.get("OMJB_GUARDRAIL_TIMEOUT", "15"))
    token_env = cli_token_env if cli_token_env is not None else file_config.get(
        "token_env", env.get("OMJB_GUARDRAIL_TOKEN_ENV", "OMJB_GUARDRAIL_TOKEN"))
    if not isinstance(endpoint, str) or not endpoint.strip():
        raise ValueError("endpoint is required via --endpoint, config file, or OMJB_GUARDRAIL_ENDPOINT")
    if isinstance(timeout, bool):
        raise ValueError("timeout must be finite and positive")
    try:
        timeout = float(timeout)
    except (TypeError, ValueError) as exc:
        raise ValueError("timeout must be finite and positive") from exc
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be finite and positive")
    if (not isinstance(token_env, str) or not token_env
            or not token_env.replace("_", "A").isalnum()
            or token_env[0].isdigit()):
        raise ValueError("token_env must be a valid environment-variable name")
    return {"endpoint": endpoint, "timeout": timeout, "token_env": token_env}
