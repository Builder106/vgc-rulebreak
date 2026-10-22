"""Per-game evaluation records and replay files for later analysis and the showcase."""

import dataclasses
import gzip
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vgc_rulebreak.evaluation import EvaluationBattleResult

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class GameContext:
    """Where one game sits in an evaluation run."""

    stage: str
    variant: str
    format_id: str
    eval_seed: int
    battle_seed: tuple[int, int, int, int] | None
    candidate: str
    opponent: str
    candidate_team: str
    opponent_team: str
    candidate_role: str
    pair_index: int
    game_in_pair: int


def game_outcome(result: "EvaluationBattleResult") -> str:
    """Outcome from the candidate's side: win, loss, tie, or unfinished."""
    if result.candidate_won:
        return "win"
    if result.winner is not None:
        return "loss"
    return "tie" if result.end_reason == "tie" else "unfinished"


class GameRecorder:
    """Writes one gzipped replay per game as it finishes, and a results file at the end."""

    def __init__(self, output_dir: Path, packed_teams: dict[str, str]) -> None:
        self.output_dir = output_dir
        self.replay_dir = output_dir / "replays"
        self.replay_dir.mkdir(parents=True, exist_ok=True)
        self.packed_teams = packed_teams
        self.games: list[dict[str, Any]] = []

    def record(self, context: GameContext, result: "EvaluationBattleResult") -> str:
        game_id = f"g{len(self.games) + 1:05d}"
        replay_path = None
        if result.replay is not None:
            replay_path = f"replays/{game_id}.json.gz"
            self._write_replay(game_id, context, result.replay)

        self.games.append(
            {
                "game_id": game_id,
                **dataclasses.asdict(context),
                "result": game_outcome(result),
                "winner": result.winner,
                "end_reason": result.end_reason,
                "turns": result.turns,
                "candidate_decisions": result.candidate_decisions,
                "opponent_decisions": result.opponent_decisions,
                "candidate_protect_uses": result.candidate_protect_uses,
                "opponent_protect_uses": result.opponent_protect_uses,
                "protect_depleted": result.protect_depleted,
                "duration_seconds": round(result.duration_seconds, 3),
                "replay": replay_path,
            }
        )
        return game_id

    def finish(self, meta: dict[str, Any], summary: dict[str, Any]) -> Path:
        path = self.output_dir / "results.json"
        document = {
            "schema_version": SCHEMA_VERSION,
            "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
            **meta,
            "summary": summary,
            "games": self.games,
        }
        path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        return path

    def _write_replay(self, game_id: str, context: GameContext, replay: dict[str, Any]) -> None:
        opponent_role = "p2" if context.candidate_role == "p1" else "p1"
        players = {
            context.candidate_role: (context.candidate, context.candidate_team),
            opponent_role: (context.opponent, context.opponent_team),
        }
        document = {
            "schema_version": SCHEMA_VERSION,
            "game_id": game_id,
            "format_id": context.format_id,
            "battle_seed": context.battle_seed,
            "players": {
                role: {"name": name, "team_id": team, "team": self.packed_teams.get(team)}
                for role, (name, team) in sorted(players.items())
            },
            "log": replay["log"],
            "decisions": replay["decisions"],
        }
        payload = json.dumps(document, separators=(",", ":")).encode("utf-8")
        (self.replay_dir / f"{game_id}.json.gz").write_bytes(gzip.compress(payload, mtime=0))
