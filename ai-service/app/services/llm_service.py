import json
import re
import time
from typing import TypeVar, Type

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel

from app.config import settings

T = TypeVar("T", bound=BaseModel)


def get_llm():
    provider = settings.LLM_PROVIDER
    model = settings.LLM_MODEL

    if provider == "openai":
        return ChatOpenAI(model=model, api_key=settings.OPENAI_API_KEY)
    elif provider == "anthropic":
        return ChatAnthropic(model=model, api_key=settings.ANTHROPIC_API_KEY)
    elif provider == "openrouter":
        return ChatOpenAI(
            model=model,
            api_key=settings.OPENROUTER_API_KEY,
            base_url=settings.OPENROUTER_BASE_URL,
        )
    elif provider == "opencode":
        # OpenCode AI gateway (https://opencode.ai). Exposes an
        # OpenAI-compatible /chat/completions endpoint, so we reuse
        # ChatOpenAI with the gateway base URL.
        base_url = settings.OPENCODE_BASE_URL or "https://opencode.ai/zen/v1"
        return ChatOpenAI(
            model=model,
            api_key=settings.OPENCODE_API_KEY,
            base_url=base_url,
        )
    elif provider == "google":
        # Google Gemini via OpenAI-compatible endpoint.
        from langchain_openai import ChatOpenAI as _ChatOpenAI
        base_url = settings.GOOGLE_BASE_URL or "https://generativelanguage.googleapis.com/v1beta/openai/"
        return _ChatOpenAI(
            model=model,
            api_key=settings.GOOGLE_API_KEY,
            base_url=base_url,
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")


def analyze_text(prompt: str) -> str:
    llm = get_llm()
    response = llm.invoke(prompt)
    return response.content


def analyze_structured(prompt: str, schema: Type[T], max_retries: int = 3) -> T:
    last_error = None
    for attempt in range(max_retries):
        try:
            schema_json = schema.model_json_schema()
            structured_prompt = f"""{prompt}

IMPORTANT: Respond with ONLY valid JSON matching this schema.
Do not include any explanation, markdown, or code fences.

JSON Schema:
{json.dumps(schema_json, indent=2)}

JSON Response:"""

            llm = get_llm()
            response = llm.invoke(structured_prompt)
            text = response.content.strip()

            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            text = text.strip()

            parsed = json.loads(text)
            return schema.model_validate(parsed)

        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                time.sleep(1 * (attempt + 1))
            continue

    raise ValueError(
        f"Failed to parse LLM response as {schema.__name__} after {max_retries} attempts. "
        f"Last error: {last_error}"
    )
