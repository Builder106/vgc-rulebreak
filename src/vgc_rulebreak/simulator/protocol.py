"""Protocol formatting and message parsing for Pokemon Showdown battle stream."""

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BattleCommand:
    """Formatter for commands sent to Showdown's simulate-battle stdin."""

    @staticmethod
    def start(format_id: str, seed: tuple[int, int, int, int] | None = None) -> str:
        payload: dict[str, Any] = {"formatid": format_id}
        if seed is not None:
            payload["seed"] = list(seed)
        return f">start {json.dumps(payload)}"

    @staticmethod
    def player(slot: str, name: str, team: str | None = None) -> str:
        payload: dict[str, Any] = {"name": name}
        if team is not None:
            payload["team"] = team
        return f">player {slot} {json.dumps(payload)}"

    @staticmethod
    def choose(slot: str, choice: str) -> str:
        clean_choice = choice.strip()
        return f">{slot} {clean_choice}"


@dataclass(frozen=True)
class ParsedMessage:
    """Parsed representation of a protocol line emitted by Showdown."""

    raw: str
    msg_type: str
    args: tuple[str, ...]
    kwargs: dict[str, str]


def parse_message_line(line: str) -> ParsedMessage | None:
    """Parse a single Showdown protocol line.

    Showdown lines follow '|type|arg1|arg2|[key] value'.
    Empty lines or lines not starting with '|' are preserved or skipped.
    """
    stripped = line.strip()
    if not stripped.startswith("|"):
        return None

    parts = stripped.split("|")[1:]
    if not parts:
        return None

    msg_type = parts[0]
    args: list[str] = []
    kwargs: dict[str, str] = {}

    for part in parts[1:]:
        if part.startswith("[") and "]" in part:
            idx = part.find("]")
            key = part[1:idx].strip()
            val = part[idx + 1 :].strip()
            kwargs[key] = val
        else:
            args.append(part)

    return ParsedMessage(raw=stripped, msg_type=msg_type, args=tuple(args), kwargs=kwargs)
