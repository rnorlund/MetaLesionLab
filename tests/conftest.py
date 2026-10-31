"""No test reaches Claude: Ask Socrates' stand-in (metalesionlab/claude_api.py) finds no key."""
import pytest

from metalesionlab import claude_api


@pytest.fixture(autouse=True)
def no_claude_key(tmp_path, monkeypatch):
    monkeypatch.setattr(claude_api, "KEY_FILE", tmp_path / "no-anthropic-env")
    for var in ("ANTHROPIC_API_KEY", "ANTHROPIC_WORKSPACE_ID", "MLL_CLAUDE_LEDGER"):
        monkeypatch.delenv(var, raising=False)
