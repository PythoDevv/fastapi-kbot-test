from __future__ import annotations

import sys
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent / ".env"
VALID_MODES = {"webhook", "polling", "disabled"}
MODE_ENV_BY_BOT = {
    "kitobxon": "KITOBXON_MODE",
    "kitobmillatbot": "KITOBMILLATBOT_MODE",
    "millatchiroqlaribot": "MILLATCHIROQLARIBOT_MODE",
    "barakali_tanlov_bot": "BARAKALI_TANLOV_BOT_MODE",
}


def _read_env_lines() -> list[str]:
    if not ENV_PATH.exists():
        raise FileNotFoundError(f"{ENV_PATH} not found")
    return ENV_PATH.read_text(encoding="utf-8").splitlines()


def _extract_current_modes(lines: list[str]) -> dict[str, str]:
    current: dict[str, str] = {}
    for bot_name, env_key in MODE_ENV_BY_BOT.items():
        current[bot_name] = "webhook"
        prefix = f"{env_key}="
        for line in lines:
            if line.startswith(prefix):
                current[bot_name] = line[len(prefix):].strip() or "webhook"
                break
    return current


def _parse_assignments(args: list[str]) -> dict[str, str]:
    assignments: dict[str, str] = {}
    for arg in args:
        if "=" not in arg:
            raise ValueError(f"Invalid argument '{arg}'. Use bot_name=mode.")
        bot_name, mode = arg.split("=", 1)
        bot_name = bot_name.strip().lower()
        mode = mode.strip().lower()
        if bot_name not in MODE_ENV_BY_BOT:
            allowed = ", ".join(MODE_ENV_BY_BOT)
            raise ValueError(f"Unknown bot '{bot_name}'. Allowed: {allowed}")
        if mode not in VALID_MODES:
            allowed = ", ".join(sorted(VALID_MODES))
            raise ValueError(f"Unknown mode '{mode}'. Allowed: {allowed}")
        assignments[MODE_ENV_BY_BOT[bot_name]] = mode
    return assignments


def _apply_updates(lines: list[str], updates: dict[str, str]) -> list[str]:
    updated_lines = list(lines)
    for env_key, value in updates.items():
        prefix = f"{env_key}="
        replaced = False
        for index, line in enumerate(updated_lines):
            if line.startswith(prefix):
                updated_lines[index] = f"{env_key}={value}"
                replaced = True
                break
        if not replaced:
            updated_lines.append(f"{env_key}={value}")
    return updated_lines


def _print_status(lines: list[str]) -> None:
    current = _extract_current_modes(lines)
    print("Current bot modes:")
    for bot_name in MODE_ENV_BY_BOT:
        print(f"  {bot_name}={current[bot_name]}")
    polling_bots = [name for name, mode in current.items() if mode == "polling"]
    webhook_bots = [name for name, mode in current.items() if mode == "webhook"]
    disabled_bots = [name for name, mode in current.items() if mode == "disabled"]
    print()
    print(f"Webhook bots: {', '.join(webhook_bots) if webhook_bots else '-'}")
    print(f"Polling bots: {', '.join(polling_bots) if polling_bots else '-'}")
    print(f"Disabled bots: {', '.join(disabled_bots) if disabled_bots else '-'}")
    print()
    print("Next steps:")
    print("  1. Restart FastAPI/webhook service for webhook bots.")
    print("  2. Run `python3 main_polling_selected.py` for polling bots.")


def main() -> int:
    try:
        lines = _read_env_lines()
        args = sys.argv[1:]
        if not args or args == ["show"]:
            _print_status(lines)
            return 0

        updates = _parse_assignments(args)
        updated_lines = _apply_updates(lines, updates)
        ENV_PATH.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")
        print(f"Updated {ENV_PATH.name}")
        _print_status(updated_lines)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        print(
            "Usage: python3 manage_bot_modes.py "
            "kitobmillatbot=webhook kitobxon=polling millatchiroqlaribot=disabled",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
