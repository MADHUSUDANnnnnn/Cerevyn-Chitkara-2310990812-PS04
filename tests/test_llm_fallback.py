"""
test_llm_fallback.py - Tests verifying graceful fallback to TemplateClient
under various provider failure modes (invalid JSON, timeouts, rate limits, unconfigured key).
Mocks external OpenAI API calls so tests run deterministically and offline.
"""

from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
import httpx
from openai import APITimeoutError, RateLimitError
from app.config import settings
from app.schemas import LLMOutputSchema
from app.services.llm import OpenAICompatibleClient, TemplateClient


def test_template_client_direct_generation():
    client = TemplateClient()
    output, source = client.generate_draft(
        message="Production database cluster unresponsive.",
        category="Technical",
        priority="high",
        kb_article={"id": "KB-005", "content": "Verify Azure Service Health for regional incidents."},
    )
    assert isinstance(output, LLMOutputSchema)
    assert source == "template"
    assert "Technical" in output.summary
    assert "Azure Support" in output.draft_response
    assert "Verify Azure Service Health" in output.draft_response


def test_llm_unconfigured_uses_template():
    with patch.object(settings, "GROQ_API_KEY", None):
        client = OpenAICompatibleClient()
        output, source = client.generate_draft(
            message="Question regarding annual billing cycle.",
            category="Billing",
            priority="low",
            kb_article=None,
        )
        assert isinstance(output, LLMOutputSchema)
        assert source == "template"
        assert "Billing" in output.summary


def test_llm_invalid_json_fallback_to_template():
    mock_choice = MagicMock()
    mock_choice.message.content = "Malformed raw non-json text: I am an AI and here is your answer."
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    with patch.object(settings, "GROQ_API_KEY", "dummy-key-for-test"), \
         patch.object(settings, "LLM_MODEL", "dummy-model"), \
         patch("openai.resources.chat.completions.Completions.create", return_value=mock_response):

        client = OpenAICompatibleClient()
        output, source = client.generate_draft(
            message="Need help resetting contractor credentials.",
            category="Access",
            priority="medium",
        )

        assert isinstance(output, LLMOutputSchema)
        assert source == "template"
        assert "Access" in output.summary


def test_llm_timeout_fallback_to_template():
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    timeout_err = APITimeoutError(request=request)

    with patch.object(settings, "GROQ_API_KEY", "dummy-key-for-test"), \
         patch.object(settings, "LLM_MODEL", "dummy-model"), \
         patch("openai.resources.chat.completions.Completions.create", side_effect=timeout_err):

        client = OpenAICompatibleClient()
        output, source = client.generate_draft(
            message="Urgent outage on load balancer.",
            category="Technical",
            priority="high",
        )

        assert isinstance(output, LLMOutputSchema)
        assert source == "template"


def test_llm_rate_limit_fallback_to_template():
    response = httpx.Response(
        status_code=429,
        request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions"),
    )
    rate_limit_err = RateLimitError(message="429 Rate limit exceeded", response=response, body=None)

    with patch.object(settings, "GROQ_API_KEY", "dummy-key-for-test"), \
         patch.object(settings, "LLM_MODEL", "dummy-model"), \
         patch("time.sleep", return_value=None), \
         patch("openai.resources.chat.completions.Completions.create", side_effect=rate_limit_err):

        client = OpenAICompatibleClient()
        output, source = client.generate_draft(
            message="Customer query about data retention.",
            category="General",
            priority="low",
        )

        assert isinstance(output, LLMOutputSchema)
        assert source == "template"


def test_end_to_end_api_fallback_when_llm_fails(client: TestClient):
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    timeout_err = APITimeoutError(request=request)

    with patch.object(settings, "GROQ_API_KEY", "dummy-key"), \
         patch.object(settings, "LLM_MODEL", "dummy-model"), \
         patch("openai.resources.chat.completions.Completions.create", side_effect=timeout_err):

        response = client.post(
            "/tickets",
            json={
                "ticket_id": "TCK-FALLBACK-001",
                "message": "Production container crash loop.",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["draft_source"] == "template"
        assert data["ticket_id"] == "TCK-FALLBACK-001"
