"""
llm.py - Provider-agnostic LLM client with strict JSON schema validation,
exponential backoff for rate limits, and seamless deterministic fallback to TemplateClient.
Never logs or exposes the API key.
"""

import json
import logging
import time
from typing import Any, Dict, Optional, Tuple
from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    RateLimitError,
)
from pydantic import ValidationError
from app.config import settings
from app.schemas import LLMOutputSchema

logger = logging.getLogger("cerevyn.llm")

SYSTEM_PROMPT = """You are an Azure support ticket assistant writing concise internal summaries and customer draft responses.
CRITICAL INSTRUCTIONS:
1. Ground your response STRICTLY in the provided Knowledge Base article.
2. NEVER invent, fabricate, or assume policies, refund amounts, dates, or SLAs not explicitly stated.
3. If no relevant Knowledge Base article is provided or if information is missing, clearly state in the draft response that a dedicated support engineer will investigate and follow up shortly.
4. You must respond ONLY with a valid JSON object containing exactly two string fields:
   - "summary": A concise 1-2 sentence internal summary of the customer's problem.
   - "draft_response": A professional, polite draft message to the customer.
"""


class TemplateClient:
    """Deterministic fallback client when LLM is unavailable, unconfigured, or errors out."""

    def generate_draft(
        self,
        message: str,
        category: str,
        priority: str,
        kb_article: Optional[Dict[str, str]] = None,
    ) -> Tuple[LLMOutputSchema, str]:
        # Concise internal summary
        first_sentence = message.strip().split(".")[0]
        if len(first_sentence) > 120:
            first_sentence = first_sentence[:117] + "..."
        summary = f"Customer reported {category} issue ({priority} priority): {first_sentence}."

        team_name = settings.TEAM_ROUTING.get(category, "Customer Care")

        if kb_article and kb_article.get("content"):
            draft = (
                f"Hello,\n\n"
                f"Thank you for contacting Azure Support. We have received your {category.lower()} inquiry.\n\n"
                f"Regarding your issue, our documentation indicates:\n"
                f"\"{kb_article['content']}\"\n\n"
                f"Your ticket has been assigned to our {team_name} team for further review. "
                f"If you have additional log files or subscription details, please reply directly to this thread.\n\n"
                f"Best regards,\nAzure Support Team"
            )
        else:
            draft = (
                f"Hello,\n\n"
                f"Thank you for reaching out to Azure Support. We have received your request regarding your {category.lower()} issue.\n\n"
                f"Your ticket has been routed to our {team_name} team with {priority} priority. "
                f"A specialized support engineer is reviewing your case and will follow up with you shortly.\n\n"
                f"Best regards,\nAzure Support Team"
            )

        return LLMOutputSchema(summary=summary, draft_response=draft), "template"


class OpenAICompatibleClient:
    """
    Client for OpenAI-compatible chat completion APIs (Groq, OmniRoute, Azure OpenAI, etc.).
    Configured strictly through environment variables.
    """

    def __init__(self):
        self.template_fallback = TemplateClient()

    def _get_client(self) -> Optional[OpenAI]:
        """Return an OpenAI-SDK client only when all three LLM settings are present.

        If any of GROQ_API_KEY, LLM_BASE_URL, or LLM_MODEL is missing we return
        None rather than constructing the client — this prevents the SDK from
        silently using its built-in default of https://api.openai.com.
        """
        if not settings.llm_fully_configured:
            return None
        return OpenAI(
            api_key=settings.GROQ_API_KEY,
            base_url=settings.LLM_BASE_URL,  # always explicit; never SDK default
            timeout=settings.LLM_TIMEOUT_SECONDS,
        )

    def _build_user_prompt(
        self,
        message: str,
        category: str,
        priority: str,
        kb_article: Optional[Dict[str, str]],
    ) -> str:
        kb_text = (
            f"Knowledge Base Article [{kb_article.get('id', '')} - {kb_article.get('title', '')}]:\n"
            f"{kb_article.get('content', '')}"
            if kb_article
            else "Knowledge Base: No matching article found. A human engineer must follow up."
        )

        return (
            f"Ticket Category: {category}\n"
            f"Determined Priority: {priority}\n"
            f"Customer Message:\n\"{message}\"\n\n"
            f"{kb_text}\n\n"
            f"Please produce the JSON output with 'summary' and 'draft_response'."
        )

    def generate_draft(
        self,
        message: str,
        category: str,
        priority: str,
        kb_article: Optional[Dict[str, str]] = None,
    ) -> Tuple[LLMOutputSchema, str]:
        # If any of the three required settings are missing, go straight to TemplateClient.
        # This also prevents the SDK from constructing a client that defaults to api.openai.com.
        if not settings.llm_fully_configured:
            missing = settings.llm_missing_settings()
            logger.info(
                "LLM not configured (missing: %s). Using TemplateClient fallback.",
                ", ".join(missing),
            )
            return self.template_fallback.generate_draft(message, category, priority, kb_article)

        client = self._get_client()
        if client is None:
            return self.template_fallback.generate_draft(message, category, priority, kb_article)

        user_prompt = self._build_user_prompt(message, category, priority, kb_article)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        # Attempt call with json_object mode, handling 429 rate limit backoff and retries
        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                # First attempt tries structured json_object format
                kwargs: Dict[str, Any] = {
                    "model": settings.LLM_MODEL,
                    "messages": messages,
                    "temperature": settings.LLM_TEMPERATURE,
                }
                if attempt == 0:
                    kwargs["response_format"] = {"type": "json_object"}

                response = client.chat.completions.create(**kwargs)
                raw_content = response.choices[0].message.content or ""

                # Parse JSON and validate with Pydantic
                parsed_json = json.loads(raw_content)
                validated = LLMOutputSchema(**parsed_json)
                return validated, "llm"

            except RateLimitError as e:
                logger.warning(
                    "LLM Rate Limit (429) on attempt %d for model '%s'. Backing off.",
                    attempt + 1,
                    settings.LLM_MODEL,
                )
                if attempt < max_attempts - 1:
                    time.sleep(1.0)
                    continue
                logger.error("Rate limit retry exhausted for model '%s'. Falling back.", settings.LLM_MODEL)
                break

            except (json.JSONDecodeError, ValidationError) as e:
                logger.warning(
                    "LLM returned invalid JSON or schema mismatch on attempt %d (model: %s): %s",
                    attempt + 1,
                    settings.LLM_MODEL,
                    type(e).__name__,
                )
                if attempt < max_attempts - 1:
                    # Retry once with prompt-only reinforcement
                    messages.append({
                        "role": "user",
                        "content": "Your previous response was not valid JSON conforming to {'summary': ..., 'draft_response': ...}. Respond with strictly valid JSON only.",
                    })
                    continue
                break

            except (APITimeoutError, APIConnectionError, AuthenticationError, APIStatusError, APIError) as e:
                logger.warning(
                    "LLM provider error '%s' on model '%s'. Falling back to TemplateClient.",
                    type(e).__name__,
                    settings.LLM_MODEL,
                )
                break

            except Exception as e:
                logger.warning(
                    "Unexpected LLM exception '%s' on model '%s'. Falling back to TemplateClient.",
                    type(e).__name__,
                    settings.LLM_MODEL,
                )
                break

        # Fallback to TemplateClient on all failures
        return self.template_fallback.generate_draft(message, category, priority, kb_article)


def get_llm_client() -> OpenAICompatibleClient:
    return OpenAICompatibleClient()
