"""
test_health_llm.py - Tests for the /health/llm configuration guard.

Requirements:
  - configured=True only when GROQ_API_KEY, LLM_BASE_URL, and LLM_MODEL are ALL set.
  - If any are missing: configured=False, reachable=False, missing_settings lists the
    absent setting *names* (never their values), and no network call is made.
  - When all three are present the endpoint probes the LLM and returns the result.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db import get_db
from app.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(db_session):
    """Return a TestClient wired to the in-memory test DB."""
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests: all three settings missing
# ---------------------------------------------------------------------------

def test_health_llm_all_missing_returns_not_configured(client: TestClient, monkeypatch):
    """When GROQ_API_KEY, LLM_BASE_URL, and LLM_MODEL are all absent the endpoint
    must return configured=False, list all three setting names, and make no
    network call."""
    monkeypatch.setattr(settings, "GROQ_API_KEY", None)
    monkeypatch.setattr(settings, "LLM_BASE_URL", None)
    monkeypatch.setattr(settings, "LLM_MODEL", None)

    # Patch OpenAI so any accidental construction raises immediately
    with patch("app.routes.health.OpenAI") as mock_openai:
        res = client.get("/health/llm")

    assert res.status_code == 200
    data = res.json()

    assert data["configured"] is False
    assert data["reachable"] is False

    missing = data["missing_settings"]
    assert set(missing) == {"GROQ_API_KEY", "LLM_BASE_URL", "LLM_MODEL"}

    # SDK client must NOT have been constructed
    mock_openai.assert_not_called()

    # Message should name the missing settings but must not contain any key value
    assert "GROQ_API_KEY" in data["message"]
    assert "LLM_BASE_URL" in data["message"]
    assert "LLM_MODEL" in data["message"]


# ---------------------------------------------------------------------------
# Tests: partial missing — key present, URL and model absent
# ---------------------------------------------------------------------------

def test_health_llm_missing_url_and_model(client: TestClient, monkeypatch):
    """When only GROQ_API_KEY is set (LLM_BASE_URL and LLM_MODEL missing) the
    endpoint must still return configured=False and name exactly the two absent
    settings — it must NOT fall through to construct an SDK client."""
    monkeypatch.setattr(settings, "GROQ_API_KEY", "test-key-value")
    monkeypatch.setattr(settings, "LLM_BASE_URL", None)
    monkeypatch.setattr(settings, "LLM_MODEL", None)

    with patch("app.routes.health.OpenAI") as mock_openai:
        res = client.get("/health/llm")

    assert res.status_code == 200
    data = res.json()

    assert data["configured"] is False
    assert data["reachable"] is False
    assert set(data["missing_settings"]) == {"LLM_BASE_URL", "LLM_MODEL"}
    assert "GROQ_API_KEY" not in data["missing_settings"]

    mock_openai.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: partial missing — URL absent only
# ---------------------------------------------------------------------------

def test_health_llm_missing_only_url(client: TestClient, monkeypatch):
    """When GROQ_API_KEY and LLM_MODEL are set but LLM_BASE_URL is absent the
    endpoint must return configured=False naming only LLM_BASE_URL, and must
    not construct an SDK client (which would default to api.openai.com)."""
    monkeypatch.setattr(settings, "GROQ_API_KEY", "test-key-value")
    monkeypatch.setattr(settings, "LLM_BASE_URL", None)
    monkeypatch.setattr(settings, "LLM_MODEL", "llama3-8b-8192")

    with patch("app.routes.health.OpenAI") as mock_openai:
        res = client.get("/health/llm")

    assert res.status_code == 200
    data = res.json()

    assert data["configured"] is False
    assert data["reachable"] is False
    assert data["missing_settings"] == ["LLM_BASE_URL"]

    mock_openai.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: partial missing — model absent only
# ---------------------------------------------------------------------------

def test_health_llm_missing_only_model(client: TestClient, monkeypatch):
    """When GROQ_API_KEY and LLM_BASE_URL are set but LLM_MODEL is absent the
    endpoint must return configured=False naming only LLM_MODEL."""
    monkeypatch.setattr(settings, "GROQ_API_KEY", "test-key-value")
    monkeypatch.setattr(settings, "LLM_BASE_URL", "https://api.groq.com/openai/v1")
    monkeypatch.setattr(settings, "LLM_MODEL", None)

    with patch("app.routes.health.OpenAI") as mock_openai:
        res = client.get("/health/llm")

    assert res.status_code == 200
    data = res.json()

    assert data["configured"] is False
    assert data["reachable"] is False
    assert data["missing_settings"] == ["LLM_MODEL"]

    mock_openai.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: fully configured — reachable (mocked success)
# ---------------------------------------------------------------------------

def test_health_llm_fully_configured_reachable(client: TestClient, monkeypatch):
    """When all three settings are present and the LLM probe succeeds the
    endpoint must return configured=True, reachable=True, and missing_settings=[]."""
    monkeypatch.setattr(settings, "GROQ_API_KEY", "test-key-value")
    monkeypatch.setattr(settings, "LLM_BASE_URL", "https://api.groq.com/openai/v1")
    monkeypatch.setattr(settings, "LLM_MODEL", "llama3-8b-8192")

    mock_client_instance = MagicMock()
    mock_client_instance.models.list.return_value = MagicMock()

    with patch("app.routes.health.OpenAI", return_value=mock_client_instance) as mock_openai:
        res = client.get("/health/llm")

    assert res.status_code == 200
    data = res.json()

    assert data["configured"] is True
    assert data["reachable"] is True
    assert data["missing_settings"] == []

    # SDK was constructed exactly once with the explicit base_url (not the SDK default)
    mock_openai.assert_called_once()
    call_kwargs = mock_openai.call_args.kwargs
    assert call_kwargs["base_url"] == "https://api.groq.com/openai/v1"
    assert "api_key" in call_kwargs


# ---------------------------------------------------------------------------
# Tests: fully configured — unreachable (mocked network error)
# ---------------------------------------------------------------------------

def test_health_llm_fully_configured_unreachable(client: TestClient, monkeypatch):
    """When all three settings are present but the LLM probe fails the endpoint
    must return configured=True but reachable=False."""
    monkeypatch.setattr(settings, "GROQ_API_KEY", "test-key-value")
    monkeypatch.setattr(settings, "LLM_BASE_URL", "https://api.groq.com/openai/v1")
    monkeypatch.setattr(settings, "LLM_MODEL", "llama3-8b-8192")

    mock_client_instance = MagicMock()
    mock_client_instance.models.list.side_effect = ConnectionError("refused")

    with patch("app.routes.health.OpenAI", return_value=mock_client_instance):
        res = client.get("/health/llm")

    assert res.status_code == 200
    data = res.json()

    assert data["configured"] is True
    assert data["reachable"] is False
    assert data["missing_settings"] == []


# ---------------------------------------------------------------------------
# Tests: missing_settings response field never leaks setting values
# ---------------------------------------------------------------------------

def test_health_llm_response_contains_no_secret_values(client: TestClient, monkeypatch):
    """The response body must never contain the actual value of GROQ_API_KEY."""
    secret = "sk-very-secret-groq-key-12345"
    monkeypatch.setattr(settings, "GROQ_API_KEY", secret)
    monkeypatch.setattr(settings, "LLM_BASE_URL", None)
    monkeypatch.setattr(settings, "LLM_MODEL", None)

    with patch("app.routes.health.OpenAI"):
        res = client.get("/health/llm")

    assert res.status_code == 200
    # The raw response text must not contain the secret key value
    assert secret not in res.text
