"""High-level BattleSession interface over a Showdown BattleStream."""

import contextlib
import json
from dataclasses import dataclass
from typing import Any

from vgc_rulebreak.simulator.process import BattleStream
from vgc_rulebreak.simulator.protocol import BattleCommand, ParsedMessage, parse_message_line


@dataclass
class BattleTurnResult:
    """Result of executing a battle turn or step."""

    turn: int
    messages: list[ParsedMessage]
    p1_request: dict[str, Any] | None
    p2_request: dict[str, Any] | None
    is_ended: bool
    winner: str | None


class BattleSession:
    """Coordinates player choices and log message collection for a single battle."""

    def __init__(self, stream: BattleStream) -> None:
        self.stream = stream
        self.turn: int = 0
        self.is_ended: bool = False
        self.winner: str | None = None
        self.p1_request: dict[str, Any] | None = None
        self.p2_request: dict[str, Any] | None = None
        self.history: list[ParsedMessage] = []

    def start(
        self,
        format_id: str,
        p1_name: str,
        p1_team: str,
        p2_name: str,
        p2_team: str,
        seed: tuple[int, int, int, int] | None = None,
    ) -> list[ParsedMessage]:
        """Initialize the battle and read setup messages up to initial requests."""
        self.stream.send(BattleCommand.start(format_id, seed))
        self.stream.send(BattleCommand.player("p1", p1_name, p1_team))
        self.stream.send(BattleCommand.player("p2", p2_name, p2_team))

        initial_messages = self._read_until_requests_or_end()
        return initial_messages

    def step(self, p1_choice: str, p2_choice: str) -> BattleTurnResult:
        """Send choices for both players and consume turn messages."""
        if self.is_ended:
            raise RuntimeError("Cannot step an ended battle.")

        self.stream.send(BattleCommand.choose("p1", p1_choice))
        self.stream.send(BattleCommand.choose("p2", p2_choice))

        turn_messages = self._read_until_requests_or_end()
        return BattleTurnResult(
            turn=self.turn,
            messages=turn_messages,
            p1_request=self.p1_request,
            p2_request=self.p2_request,
            is_ended=self.is_ended,
            winner=self.winner,
        )

    def _read_until_requests_or_end(self) -> list[ParsedMessage]:
        collected: list[ParsedMessage] = []
        target_slot: str | None = None

        while True:
            line = self.stream.read_line()
            if line is None:
                break

            parsed = parse_message_line(line)
            if parsed is None:
                continue

            collected.append(parsed)
            self.history.append(parsed)

            if parsed.msg_type == "turn" and parsed.args:
                with contextlib.suppress(ValueError):
                    self.turn = int(parsed.args[0])

            elif parsed.msg_type == "win" and parsed.args:
                self.is_ended = True
                self.winner = parsed.args[0]
                break

            elif parsed.msg_type == "tie":
                self.is_ended = True
                self.winner = None
                break

            elif parsed.msg_type == "split" and parsed.args:
                target_slot = parsed.args[0]

            elif parsed.msg_type == "request" and parsed.args:
                payload_str = parsed.args[0]
                if payload_str.strip():
                    try:
                        req_data = json.loads(payload_str)
                        if target_slot == "p1":
                            self.p1_request = req_data
                        elif target_slot == "p2":
                            self.p2_request = req_data
                    except json.JSONDecodeError:
                        pass
                # Once requests for both active players are collected or wait condition met
                if self.p1_request and self.p2_request:
                    break

        return collected
