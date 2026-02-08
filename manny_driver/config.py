"""Configuration for manny-driver."""
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


# Pricing per million tokens: (input, output)
MODEL_PRICING = {
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-2.5-flash": (0.30, 2.50),
    "claude-sonnet-4-20250514": (3.00, 15.00),
    "claude-haiku-4-5-20251001": (0.80, 4.00),
    "gpt-4o-mini": (0.15, 0.60),
}


def get_token_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate cost in USD for a given model and token counts."""
    prices = MODEL_PRICING.get(model, (0.10, 0.40))  # default to flash-lite pricing
    return input_tokens * prices[0] / 1_000_000 + output_tokens * prices[1] / 1_000_000


@dataclass
class DriverConfig:
    """Driver configuration."""

    # LLM provider settings
    provider: str = "auto"
    model: Optional[str] = None
    temperature: float = 0.3

    # Account
    account_id: str = "main"

    # Agent limits
    max_tool_calls_per_turn: int = 50
    monitoring_interval_seconds: int = 30
    conversation_window_size: int = 40

    # MCP server
    server_script: str = "server.py"
    server_cwd: Optional[str] = None

    # Cost budget
    max_session_cost_usd: float = 1.0  # Stop driver if estimated cost exceeds this

    # Display
    verbose: bool = False
    monitor_only: bool = False

    @property
    def resolved_model(self) -> str:
        """Get the model name, using provider defaults if not specified."""
        if self.model:
            return self.model
        defaults = {
            "anthropic": "claude-sonnet-4-20250514",
            "gemini": "gemini-2.5-flash-lite",
            "ollama": "hermes3:8b-llama3.1-q4_K_M",
            "openai": "gpt-4o-mini",
        }
        return defaults.get(self.provider, "claude-sonnet-4-20250514")

    @property
    def api_key(self) -> Optional[str]:
        """Get the API key for the current provider."""
        env_vars = {
            "anthropic": "ANTHROPIC_API_KEY",
            "gemini": "GEMINI_API_KEY",
            "openai": "OPENAI_API_KEY",
        }
        var = env_vars.get(self.provider)
        return os.environ.get(var) if var else None


def detect_provider() -> str:
    """Auto-detect the best available provider based on API keys.

    Gemini is checked first because ANTHROPIC_API_KEY may be set by
    Claude Code's own environment but not usable by subprocesses.
    """
    if os.environ.get("GEMINI_API_KEY"):
        return "gemini"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    # Check if Ollama is reachable
    try:
        import httpx
        resp = httpx.get(
            f"{os.environ.get('OLLAMA_HOST', 'http://localhost:11434')}/api/tags",
            timeout=2,
        )
        if resp.status_code == 200:
            return "ollama"
    except Exception:
        pass
    raise RuntimeError(
        "No LLM provider found. Set ANTHROPIC_API_KEY, GEMINI_API_KEY, "
        "OPENAI_API_KEY, or ensure Ollama is running."
    )


def load_config(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    account: Optional[str] = None,
    verbose: bool = False,
    monitor_only: bool = False,
) -> DriverConfig:
    """Load driver config, merging CLI args with config.yaml."""
    config = DriverConfig()

    # Load from config.yaml driver section if it exists
    config_path = Path(__file__).parent.parent / "config.yaml"
    if config_path.exists():
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
        driver_data = data.get("driver", {})
        if driver_data:
            for k, v in driver_data.items():
                if hasattr(config, k):
                    setattr(config, k, v)

        # Set server_cwd to the project root
        config.server_cwd = str(config_path.parent)

    # CLI overrides
    if provider:
        config.provider = provider
    elif not config.provider or config.provider == "auto":
        config.provider = detect_provider()

    if model:
        config.model = model
    if account:
        config.account_id = account
    config.verbose = verbose
    config.monitor_only = monitor_only

    # Auto-tune conversation window for local models with smaller context
    if config.provider == "ollama" and config.conversation_window_size > 10:
        config.conversation_window_size = 10

    return config
