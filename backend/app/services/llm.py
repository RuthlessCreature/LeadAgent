from __future__ import annotations

import json
import os
import re
import warnings
from typing import Any

import httpx


DEEPSEEK_DEFAULT_MODEL = "deepseek-v4-flash"
DEEPSEEK_REASONING_MODEL = "deepseek-v4-flash-thinking"
DEEPSEEK_REPORT_MODEL = "deepseek-v4-pro"
DEEPSEEK_REPORT_REASONING_MODEL = "deepseek-v4-pro-thinking"
DEEPSEEK_LEGACY_MODELS = {"deepseek-chat", "deepseek-reasoner"}


class LLMClient:
    """Small provider adapter with DeepSeek V4-oriented model routing."""

    def __init__(
        self,
        provider: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        task: str = "default",
        timeout_seconds: float | None = None,
    ) -> None:
        self.provider = (provider or os.getenv("DEFAULT_LLM", "deepseek")).strip().lower()
        self.api_key = api_key or self._get_api_key()
        self.base_url = (base_url or self._get_base_url()).rstrip("/")
        self.task = task
        self.model = model or self._get_model(task=task)
        self.timeout_seconds = timeout_seconds or float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
        if self.provider == "deepseek":
            self.timeout_seconds = float(os.getenv("DEEPSEEK_TIMEOUT_SECONDS", str(self.timeout_seconds)))
            if self.model in DEEPSEEK_LEGACY_MODELS:
                warnings.warn(
                    f"DeepSeek model '{self.model}' is a legacy alias; configure a V4 model instead.",
                    RuntimeWarning,
                    stacklevel=2,
                )

    def _get_api_key(self) -> str | None:
        keys = {
            "deepseek": os.getenv("DEEPSEEK_API_KEY"),
            "openai": os.getenv("OPENAI_API_KEY"),
            "claude": os.getenv("ANTHROPIC_API_KEY"),
            "anthropic": os.getenv("ANTHROPIC_API_KEY"),
            "minimax": os.getenv("MINIMAX_API_KEY"),
        }
        return keys.get(self.provider)

    def _get_base_url(self) -> str:
        urls = {
            "deepseek": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            "openai": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            "claude": os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1"),
            "anthropic": os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1"),
            "minimax": os.getenv("MINIMAX_BASE_URL", "https://api.minimax.chat/v1"),
        }
        return urls.get(self.provider, "")

    def _get_model(self, task: str = "default") -> str:
        if self.provider == "deepseek":
            models = {
                "default": os.getenv("DEEPSEEK_MODEL", DEEPSEEK_DEFAULT_MODEL),
                "fast": os.getenv("DEEPSEEK_MODEL", DEEPSEEK_DEFAULT_MODEL),
                "reasoning": os.getenv("DEEPSEEK_REASONING_MODEL", DEEPSEEK_REASONING_MODEL),
                "report": os.getenv("DEEPSEEK_REPORT_MODEL", DEEPSEEK_REPORT_MODEL),
                "report_reasoning": os.getenv(
                    "DEEPSEEK_REPORT_REASONING_MODEL",
                    DEEPSEEK_REPORT_REASONING_MODEL,
                ),
            }
            return models.get(task, models["default"])
        if self.provider == "openai":
            return os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
        if self.provider in {"claude", "anthropic"}:
            return os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
        if self.provider == "minimax":
            return os.getenv("MINIMAX_MODEL", "abab6.5s-chat")
        return os.getenv("LLM_MODEL", DEEPSEEK_DEFAULT_MODEL)

    def metadata(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "base_url": self.base_url,
            "model": self.model,
            "task": self.task,
            "has_api_key": bool(self.api_key),
            "deepseek_defaults": deepseek_model_defaults(),
        }

    def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        task = str(kwargs.pop("task", self.task) or self.task)
        model = str(kwargs.pop("model", "") or (self._get_model(task) if task != self.task else self.model))
        if self.provider == "deepseek":
            return self._openai_compatible_chat(messages, model=model, **kwargs)
        if self.provider == "openai":
            return self._openai_compatible_chat(messages, model=model, **kwargs)
        if self.provider in {"claude", "anthropic"}:
            return self._claude_chat(messages, model=model, **kwargs)
        if self.provider == "minimax":
            return self._minimax_chat(messages, model=model, **kwargs)
        raise ValueError(f"Unknown provider: {self.provider}")

    def chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        task: str = "default",
        retry_on_parse_error: bool = True,
        **kwargs: Any,
    ) -> dict[str, Any]:
        raw = self.chat(messages, task=task, response_format={"type": "json_object"}, **kwargs)
        try:
            parsed = parse_json_object(raw)
            if isinstance(parsed, dict):
                return parsed
        except ValueError:
            if not retry_on_parse_error:
                raise

        repair_prompt = [
            {
                "role": "system",
                "content": "Return only a valid JSON object. Do not add markdown or commentary.",
            },
            {
                "role": "user",
                "content": f"Repair this model output into valid JSON:\n{raw}",
            },
        ]
        repaired = self.chat(repair_prompt, task=task, response_format={"type": "json_object"}, **kwargs)
        parsed = parse_json_object(repaired)
        if not isinstance(parsed, dict):
            raise ValueError("LLM response was not a JSON object.")
        return parsed

    def _openai_compatible_chat(self, messages: list[dict[str, str]], model: str, **kwargs: Any) -> str:
        if not self.api_key:
            raise ValueError(f"Missing API key for provider '{self.provider}'.")
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.2),
        }
        if kwargs.get("max_tokens") is not None:
            payload["max_tokens"] = kwargs["max_tokens"]
        if kwargs.get("response_format") is not None:
            payload["response_format"] = kwargs["response_format"]
        response = httpx.post(url, headers=headers, json=payload, timeout=self.timeout_seconds)
        response.raise_for_status()
        return str(response.json()["choices"][0]["message"]["content"])

    def _claude_chat(self, messages: list[dict[str, str]], model: str, **kwargs: Any) -> str:
        if not self.api_key:
            raise ValueError("Missing API key for provider 'anthropic'.")
        url = f"{self.base_url}/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [{"role": row["role"], "content": row["content"]} for row in messages],
            "max_tokens": kwargs.get("max_tokens", 1024),
        }
        response = httpx.post(url, headers=headers, json=payload, timeout=self.timeout_seconds)
        response.raise_for_status()
        return str(response.json()["content"][0]["text"])

    def _minimax_chat(self, messages: list[dict[str, str]], model: str, **kwargs: Any) -> str:
        if not self.api_key:
            raise ValueError("Missing API key for provider 'minimax'.")
        url = f"{self.base_url}/text/chatcompletion_v2"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [{"role": row["role"], "content": row["content"]} for row in messages],
            "temperature": kwargs.get("temperature", 0.2),
        }
        response = httpx.post(url, headers=headers, json=payload, timeout=self.timeout_seconds)
        response.raise_for_status()
        return str(response.json()["choices"][0]["message"]["content"])


def deepseek_model_defaults() -> dict[str, str]:
    return {
        "default": os.getenv("DEEPSEEK_MODEL", DEEPSEEK_DEFAULT_MODEL),
        "reasoning": os.getenv("DEEPSEEK_REASONING_MODEL", DEEPSEEK_REASONING_MODEL),
        "report": os.getenv("DEEPSEEK_REPORT_MODEL", DEEPSEEK_REPORT_MODEL),
        "report_reasoning": os.getenv("DEEPSEEK_REPORT_REASONING_MODEL", DEEPSEEK_REPORT_REASONING_MODEL),
        "legacy_retirement_date": "2026-07-24",
    }


def parse_json_object(raw: str) -> Any:
    text = (raw or "").strip()
    if not text:
        raise ValueError("Empty LLM response.")
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match is None:
            raise ValueError("No JSON object found in LLM response.") from None
        return json.loads(match.group(0))


def parse_product_description(description: str, llm: LLMClient | None = None) -> dict[str, Any]:
    """Legacy Flask-compatible helper for turning a product brief into search terms."""
    client = llm or LLMClient(task="reasoning")
    prompt = {
        "role": "user",
        "content": (
            "You are a B2B export sales analyst. Analyze the product description and return a JSON object "
            "for finding buyers, not competing manufacturers. Include product_name, keywords, target_market, "
            "target_role, and search_queries. Search queries should focus on importers, distributors, "
            "wholesalers, retailers, ecommerce sellers, procurement buyers, or institutions.\n\n"
            f"Product description:\n{description}"
        ),
    }
    try:
        result = client.chat_json([prompt], task="reasoning", temperature=0.1)
        return {
            "product_name": str(result.get("product_name") or description),
            "keywords": _string_list(result.get("keywords")) or description.split(),
            "target_market": str(result.get("target_market") or ""),
            "target_role": _string_list(result.get("target_role"))
            or ["wholesaler", "distributor", "importer", "buyer"],
            "search_queries": _query_list(result.get("search_queries")),
        }
    except Exception:
        return {
            "product_name": description,
            "keywords": description.split(),
            "target_market": "",
            "target_role": ["wholesaler", "distributor", "importer", "buyer"],
            "search_queries": [],
        }


def score_lead(lead_data: dict[str, Any], icp: dict[str, Any], llm: LLMClient | None = None) -> dict[str, Any]:
    """Legacy Flask-compatible helper for LLM lead scoring."""
    client = llm or LLMClient(task="reasoning")
    prompt = {
        "role": "user",
        "content": (
            "Score whether this is a target buyer for the seller's product. Prefer buyers such as "
            "wholesalers, distributors, importers, procurement teams, retailers, ecommerce sellers, "
            "and institutions. Penalize manufacturers/factories/suppliers when they look like competitors. "
            "Return JSON with is_target, score, reason, tags, and contact_priority.\n\n"
            f"ICP:\n{json.dumps(icp, ensure_ascii=False)}\n\n"
            f"Lead:\n{json.dumps(lead_data, ensure_ascii=False)}"
        ),
    }
    try:
        result = client.chat_json([prompt], task="reasoning", temperature=0.1)
        return {
            "is_target": result.get("is_target"),
            "score": _clamp_int(result.get("score"), default=50),
            "reason": str(result.get("reason") or ""),
            "tags": _string_list(result.get("tags")),
            "contact_priority": str(result.get("contact_priority") or "medium"),
        }
    except Exception:
        return {
            "is_target": None,
            "score": 50,
            "reason": "LLM scoring failed; fallback required.",
            "tags": [],
            "contact_priority": "medium",
        }


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [part.strip() for part in re.split(r"[,;\n]", value) if part.strip()]
    return []


def _query_list(value: Any) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not isinstance(value, list):
        return rows
    for item in value:
        if isinstance(item, dict):
            query = str(item.get("query") or "").strip()
            if query:
                rows.append(
                    {
                        "platform": str(item.get("platform") or "linkedin").strip().lower(),
                        "query": query,
                        "type": str(item.get("type") or "people").strip().lower(),
                    }
                )
        elif str(item).strip():
            rows.append({"platform": "linkedin", "query": str(item).strip(), "type": "people"})
    return rows


def _clamp_int(value: Any, default: int = 50) -> int:
    try:
        score = int(float(value))
    except Exception:
        score = default
    return max(0, min(100, score))

