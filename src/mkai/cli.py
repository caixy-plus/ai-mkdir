"""CLI for mkai — AI-powered mkdir."""

import argparse
import os
import sys
import termios
import tty
from pathlib import Path

from .config import Config, ProviderConfig
from .providers import get_provider


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="mkai",
        description="Create a project directory with an AI-generated English name.",
    )
    parser.add_argument(
        "description",
        nargs="?",
        help="Natural language description of the project (e.g. '用户管理后台')",
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Interactive setup: configure AI providers",
    )
    parser.add_argument(
        "--provider", "-p",
        help="Override the default AI provider (ollama, openai, anthropic)",
    )
    parser.add_argument(
        "--base-dir", "-d",
        help="Override the base directory for project creation",
    )
    parser.add_argument(
        "--list-providers",
        action="store_true",
        help="List configured providers",
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Create directory even if it already exists (will NOT cd into existing dirs)",
    )

    args = parser.parse_args()

    if args.setup:
        _setup_wizard()
        return

    if args.list_providers:
        _list_providers()
        return

    if not args.description:
        parser.print_help(sys.stderr)
        print("\nExample: mkai '用户管理后台'", file=sys.stderr)
        raise SystemExit(1)

    # Load config
    config = Config.load()
    provider_name = args.provider or config.provider
    provider_config = config.get_provider_config(provider_name)
    provider = get_provider(provider_config)

    # Get suggestions from AI, with retry
    while True:
        print(f"\n🤖 Asking {provider_name} for name suggestions...", file=sys.stderr)
        try:
            names = provider.suggest_names(args.description)
        except SystemExit:
            raise
        except Exception as e:
            raise SystemExit(f"mkai: {e}")

        # Interactive arrow-key selection
        print(f"\nSuggestions for: {args.description}\n", file=sys.stderr)
        idx = _pick(names)
        if idx == -1:
            print("Cancelled.", file=sys.stderr)
            raise SystemExit(0)
        if idx == -2:  # retry
            continue
        selected = names[idx]
        break

    # Create directory
    base_dir = Path(args.base_dir or config.base_dir).expanduser().resolve()
    full_path = base_dir / selected

    try:
        full_path.mkdir(parents=True, exist_ok=args.force)
    except FileExistsError:
        raise SystemExit(
            f"Directory already exists: {full_path}\n"
            f"Use --force to proceed anyway (won't cd into existing dir)."
        )
    except OSError as e:
        raise SystemExit(f"Could not create directory: {e}")

    print(f"Created: {full_path}", file=sys.stderr)

    # Output cd command to stdout for shell eval
    print(f"cd {full_path}")


def _pick(names: list[str]) -> int:
    """Interactive arrow-key picker. Returns selected index, -1 if cancelled, -2 to retry."""
    if not sys.stdin.isatty():
        return _pick_fallback(names)

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    selected = 0

    def render() -> None:
        for i, name in enumerate(names):
            if i == selected:
                sys.stderr.write(f"\033[7m  ▸ {name}  \033[0m\033[K\r\n")
            else:
                sys.stderr.write(f"    {name}\033[K\r\n")
        sys.stderr.write("\r\n  ↑↓ select  ↵ confirm  r retry  q quit\033[K\r\n")
        sys.stderr.flush()

    try:
        tty.setraw(fd)
        sys.stderr.write("\033[?25l")  # Hide cursor
        render()
        while True:
            ch = sys.stdin.read(1)
            if ch == "\x1b":
                seq = sys.stdin.read(2)
                if seq == "[A":
                    selected = (selected - 1) % len(names)
                elif seq == "[B":
                    selected = (selected + 1) % len(names)
                sys.stderr.write(f"\033[{len(names) + 2}A")
                render()
            elif ch in ("\r", "\n"):
                return selected
            elif ch in ("r", "R"):
                return -2
            elif ch in ("q", "Q", "\x03"):
                return -1
    finally:
        sys.stderr.write("\033[?25h")  # Show cursor
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        print(f"\n  → {names[selected]}\n", file=sys.stderr)


def _pick_fallback(names: list[str]) -> int:
    """Number-input fallback when stdin is not a TTY."""
    for i, name in enumerate(names, 1):
        print(f"  [{i}] {name}", file=sys.stderr)
    print("  [r] retry  [q] quit", file=sys.stderr)

    while True:
        try:
            choice = input("Pick (1-{}, r=retry, q=quit): ".format(len(names)))
        except (EOFError, KeyboardInterrupt):
            return -1
        if choice.lower() == "q":
            return -1
        if choice.lower() == "r":
            return -2
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(names):
                return idx
        except ValueError:
            pass
        print(f"Invalid. Enter 1-{len(names)}, r, or q.", file=sys.stderr)


def _list_providers() -> None:
    config = Config.load()
    default = config.provider
    print("Configured providers:\n")
    for name, pc in config.providers.items():
        marker = " (default)" if name == default else ""
        key_status = "🔑" if pc.api_key else "(no key)"
        url = pc.base_url or "(built-in)"
        print(f"  {name}{marker}")
        print(f"    model: {pc.model}  key: {key_status}  url: {url}")
    print(f"\nDefault: {default}")
    print("Run `mkai --setup` to add or change providers.")


def _setup_wizard() -> None:
    print("\n=== mkai setup ===\n")
    print("Configure an AI provider for project name suggestions.\n")

    config = Config.load()

    print("Protocol types:")
    print("  1. ollama              — local models (no API key)")
    print("  2. openai-compatible   — OpenAI / DeepSeek / Groq / vLLM / any /chat/completions API")
    print("  3. anthropic           — Claude or any Anthropic Messages API\n")

    while True:
        choice = input("Pick protocol (1-3): ").strip()
        if choice in ("1", "2", "3"):
            break
        print("Invalid. Pick 1, 2, or 3.")

    if choice == "1":
        name = "ollama"
        base_url = input("Ollama URL [http://localhost:11434]: ").strip() or "http://localhost:11434"
        model = input("Model (e.g. qwen2.5:7b): ").strip() or "qwen2.5:7b"
        config.providers[name] = ProviderConfig(
            name=name, model=model, base_url=base_url
        )
    elif choice == "2":
        name = "openai"
        base_url = input("Base URL [https://api.openai.com/v1]: ").strip() or "https://api.openai.com/v1"
        api_key = input("API key (press Enter to skip): ").strip()
        model = input("Model (e.g. gpt-4o-mini, deepseek-chat, grok-3, ...): ").strip()
        if not model:
            print("Model name is required.", file=sys.stderr)
            raise SystemExit(1)
        config.providers[name] = ProviderConfig(
            name=name, model=model, api_key=api_key, base_url=base_url
        )
    else:
        name = "anthropic"
        base_url = input("Base URL [https://api.anthropic.com]: ").strip() or "https://api.anthropic.com"
        api_key = input("API key (press Enter to skip): ").strip()
        model = input("Model (e.g. claude-haiku-4-5-20251001): ").strip()
        if not model:
            print("Model name is required.", file=sys.stderr)
            raise SystemExit(1)
        config.providers[name] = ProviderConfig(
            name=name, model=model, api_key=api_key, base_url=base_url
        )

    config.provider = name
    config.save()
    print(f"\nDone! Default provider set to '{name}'.\n")
    print("To use: mkai 'project description'")
    print("To add more providers, run `mkai --setup` again.\n")

    # Check shell integration
    zshrc = Path.home() / ".zshrc"
    marker = "### mkai shell integration"
    if zshrc.exists() and marker in zshrc.read_text():
        print("Shell integration found in ~/.zshrc ✓")
    else:
        print("Tip: run ./install.sh to set up the shell cd integration.")
