"""AI provider abstraction for mkai."""

import json
import sys
from abc import ABC, abstractmethod

import requests

from .config import ProviderConfig

SYSTEM_PROMPT = """You are a project directory naming assistant. Given a project description, suggest 5 concise English directory names using only lowercase letters, numbers, and hyphens. Each 2-4 words max. Short and memorable.

Return ONLY a JSON array of strings, no other text, no markdown fences, no explanation.

Example input: "用户管理后台"
Example output: ["user-admin", "admin-panel", "user-dashboard", "account-manager", "user-backend"]"""


class Provider(ABC):
    @abstractmethod
    def suggest_names(self, description: str) -> list[str]:
        """Return 5 suggested English directory names for the description."""


class OpenAICompatibleProvider(Provider):
    """Works with OpenAI, Ollama, vLLM, and any /chat/completions endpoint."""

    def __init__(self, config: ProviderConfig):
        self.model = config.model
        self.base_url = config.base_url.rstrip("/")
        self.api_key = config.api_key

    def suggest_names(self, description: str) -> list[str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": description},
            ],
            "temperature": 0.8,
            "max_tokens": 200,
        }

        try:
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=body,
                timeout=30,
            )
            resp.raise_for_status()
        except requests.exceptions.ConnectionError:
            raise SystemExit(
                f"Could not connect to {self.base_url}. Is the server running?"
            )
        except requests.exceptions.HTTPError as e:
            detail = ""
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text[:500]
            raise SystemExit(f"API error ({resp.status_code}): {detail}")

        data = resp.json()
        content = data["choices"][0]["message"]["content"].strip()
        # Strip markdown fences if present
        if content.startswith("```"):
            content = content.split("\n", 1)[-1]
            if content.endswith("```"):
                content = content[:-3]
        return _parse_json_response(content)


class AnthropicProvider(Provider):
    DEFAULT_BASE_URL = "https://api.anthropic.com"

    def __init__(self, config: ProviderConfig):
        self.model = config.model
        self.api_key = config.api_key
        self.base_url = (config.base_url or self.DEFAULT_BASE_URL).rstrip("/")

    def suggest_names(self, description: str) -> list[str]:
        if not self.api_key:
            raise SystemExit(
                "Anthropic API key not set. Run `mkai --setup` to configure."
            )

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }

        body = {
            "model": self.model,
            "max_tokens": 20480,
            "temperature": 0.8,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": description}],
        }

        try:
            resp = requests.post(
                f"{self.base_url}/v1/messages",
                headers=headers,
                json=body,
                timeout=30,
            )
            resp.raise_for_status()
        except requests.exceptions.ConnectionError:
            raise SystemExit("Could not connect to Anthropic API. Check your network.")
        except requests.exceptions.HTTPError as e:
            detail = ""
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text[:500]
            raise SystemExit(f"Anthropic API error ({resp.status_code}): {detail}")

        data = resp.json()
        # Find the first text block (thinking models return thinking blocks too)
        text_blocks = [b["text"] for b in data["content"] if b.get("type") == "text"]
        if not text_blocks:
            raise SystemExit(
                f"Model returned no text (got types: {[b.get('type') for b in data['content']]}). "
                "Try a non-thinking model or increase max_tokens."
            )
        return _parse_json_response(text_blocks[0].strip())


def get_provider(config: ProviderConfig) -> Provider:
    if config.name == "anthropic":
        return AnthropicProvider(config)
    return OpenAICompatibleProvider(config)


def _parse_json_response(content: str) -> list[str]:
    try:
        names = json.loads(content)
    except json.JSONDecodeError:
        # Try to extract JSON array from the text
        import re

        match = re.search(r"\[.*?\]", content, re.DOTALL)
        if not match:
            print(
                f"mkai: could not parse AI response:\n{content}",
                file=sys.stderr,
            )
            raise SystemExit(1)
        try:
            names = json.loads(match.group(0))
        except json.JSONDecodeError:
            print(
                f"mkai: could not parse AI response:\n{content}",
                file=sys.stderr,
            )
            raise SystemExit(1)

    if not isinstance(names, list) or len(names) == 0:
        print(f"mkai: AI returned unexpected response: {names}", file=sys.stderr)
        raise SystemExit(1)

    # Sanitize: only lowercase, numbers, hyphens
    import re

    clean = []
    for name in names[:5]:
        name = name.lower().strip()
        name = re.sub(r"[^a-z0-9-]", "", name.replace(" ", "-"))
        name = re.sub(r"-+", "-", name).strip("-")
        if name:
            clean.append(name)

    if not clean:
        print("mkai: AI returned no usable names", file=sys.stderr)
        raise SystemExit(1)

    return clean
