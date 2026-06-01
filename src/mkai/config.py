"""Configuration management for mkai."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


def config_path() -> Path:
    xdg = os.getenv("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return Path(xdg) / "mkai" / "config.json"


@dataclass
class ProviderConfig:
    name: str
    model: str
    api_key: str = ""
    base_url: str = ""
    extra: dict = field(default_factory=dict)


@dataclass
class Config:
    provider: str = "ollama"
    base_dir: str = "."
    providers: dict[str, ProviderConfig] = field(default_factory=dict)

    @classmethod
    def load(cls) -> "Config":
        path = config_path()
        if not path.exists():
            return cls._defaults()
        raw = json.loads(path.read_text())
        return cls._from_dict(raw)

    def save(self) -> None:
        path = config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "provider": self.provider,
            "base_dir": self.base_dir,
            "providers": {
                k: {
                    "name": v.name,
                    "model": v.model,
                    "api_key": v.api_key,
                    "base_url": v.base_url,
                }
                | v.extra
                for k, v in self.providers.items()
            },
        }
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def get_provider_config(self, name: Optional[str] = None) -> ProviderConfig:
        name = name or self.provider
        if name not in self.providers:
            raise SystemExit(
                f"Provider '{name}' not configured. Run `mkai --setup` first."
            )
        return self.providers[name]

    @classmethod
    def _defaults(cls) -> "Config":
        return cls(
            provider="ollama",
            base_dir=".",
            providers={
                "ollama": ProviderConfig(
                    name="ollama",
                    model="qwen2.5:7b",
                    base_url="http://localhost:11434",
                ),
                "openai": ProviderConfig(
                    name="openai",
                    model="gpt-4o-mini",
                    base_url="https://api.openai.com/v1",
                ),
                "anthropic": ProviderConfig(
                    name="anthropic",
                    model="claude-haiku-4-5-20251001",
                ),
            },
        )

    @classmethod
    def _from_dict(cls, d: dict) -> "Config":
        providers = {}
        for name, pd in d.get("providers", {}).items():
            extra = {k: v for k, v in pd.items() if k not in ("name", "model", "api_key", "base_url")}
            providers[name] = ProviderConfig(
                name=pd.get("name", name),
                model=pd["model"],
                api_key=pd.get("api_key", ""),
                base_url=pd.get("base_url", ""),
                extra=extra,
            )
        return cls(
            provider=d.get("provider", "ollama"),
            base_dir=d.get("base_dir", "."),
            providers=providers,
        )
