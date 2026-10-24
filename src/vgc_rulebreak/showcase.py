"""Export evaluated games as static data for the public showcase.

Each replay becomes a list of turn frames: the field at the start and end of the turn, what
each side could choose (with the PP its request showed), what it chose, and the turn's events
as plain sentences. The site renders these frames and never parses the protocol itself.
"""

import gzip
import json
import re
import subprocess
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from vgc_rulebreak.pilot import PROTECTION_MOVE_IDS
from vgc_rulebreak.recovery import CHECKPOINT_NAME, summarize_recovery

SCHEMA_VERSION = 1
AGENT_ORDER = ("source", "native", "adapted")
OPPONENT_LABEL = "Baseline"
STATS = {
    "atk": "Attack",
    "def": "Defense",
    "spa": "Sp. Atk",
    "spd": "Sp. Def",
    "spe": "Speed",
    "accuracy": "accuracy",
    "evasion": "evasiveness",
}
STATUS = {
    "brn": "was burned",
    "par": "was paralyzed",
    "psn": "was poisoned",
    "tox": "was badly poisoned",
    "slp": "fell asleep",
    "frz": "was frozen solid",
}
RISE = {1: "rose", 2: "rose sharply"}
FALL = {1: "fell", 2: "fell harshly"}
IDENT = re.compile(r"^(?P<side>p[12])(?P<slot>[ab])?: (?P<name>.+)$")

Names = dict[str, dict[str, str]]


def to_id(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def load_dex_names(showdown_dir: Path, ids: dict[str, set[str]]) -> Names:
    """Display names for move, item, and ability IDs, read from the pinned simulator's Dex."""
    script = (
        "const {Dex}=require('./dist/sim');const d=Dex.mod('gen9');"
        "const ids=JSON.parse(require('fs').readFileSync(0,'utf8'));const out={};"
        "for(const [kind,list] of Object.entries(ids)){out[kind]={};"
        "for(const id of list){out[kind][id]=d[kind].get(id).name||id;}}"
        "process.stdout.write(JSON.stringify(out));"
    )
    request = json.dumps({kind: sorted(values) for kind, values in ids.items()})
    result = subprocess.run(
        ["node", "-e", script],
        cwd=showdown_dir,
        input=request,
        capture_output=True,
        text=True,
        check=True,
    )
    names: Names = json.loads(result.stdout)
    return names


def parse_condition(condition: str) -> dict[str, Any]:
    """'168/252 brn' or '0 fnt' as hit points, maximum, and status."""
    parts = condition.split()
    if parts[0] == "0":
        return {"hp": 0, "fainted": True, "status": None}
    hp, _, maxhp = parts[0].partition("/")
    status = parts[1] if len(parts) > 1 else None
    return {"hp": int(hp), "maxhp": int(maxhp or hp), "fainted": False, "status": status}


def species_of(details: str) -> str:
    return details.split(",")[0]


class FrameBuilder:
    """Replays a protocol log into turn frames with readable events."""

    def __init__(self, labels: dict[str, str]) -> None:
        self.labels = labels
        self.field: dict[str, dict[str, dict[str, Any] | None]] = {
            "p1": {"a": None, "b": None},
            "p2": {"a": None, "b": None},
        }
        self.species: dict[tuple[str, str], str] = {}
        self.players: dict[str, str] = {}
        self.prelude: list[str] = []
        self.frames: list[dict[str, Any]] = []
        self.events = self.prelude

    def who(self, ident: str) -> str:
        match = IDENT.match(ident)
        if match is None:
            return ident
        species = self.species.get((match["side"], match["name"]), match["name"])
        return f"{self.labels[match['side']]}'s {species}"

    def slot(self, ident: str) -> dict[str, Any] | None:
        match = IDENT.match(ident)
        if match is None or match["slot"] is None:
            return None
        return self.field[match["side"]][match["slot"]]

    def percent(self, ident: str) -> int:
        mon = self.slot(ident)
        if not mon or not mon.get("maxhp"):
            return 0
        return round(100 * int(mon["hp"]) / int(mon["maxhp"]))

    def apply_condition(self, ident: str, condition: str) -> None:
        mon = self.slot(ident)
        if mon is None:
            return
        parsed = parse_condition(condition)
        mon.update(parsed)

    def snapshot(self) -> dict[str, list[dict[str, Any] | None]]:
        return {
            side: [dict(mon) if mon else None for mon in (slots["a"], slots["b"])]
            for side, slots in self.field.items()
        }

    def start_turn(self, turn: int) -> None:
        self.finish()
        self.events = []
        self.frames.append({"turn": turn, "field": self.snapshot(), "events": self.events})

    def finish(self) -> None:
        """Record the field after the latest turn's events."""
        if self.frames:
            self.frames[-1]["after"] = self.snapshot()

    def say(self, text: str) -> None:
        self.events.append(text)

    def feed(self, line: str) -> None:
        parts = line.split("|")
        if len(parts) < 2:
            return
        kind, args = parts[1], parts[2:]
        tags = [a for a in args if a.startswith("[")]
        source = next((t[7:] for t in tags if t.startswith("[from] ")), None)
        if source:
            source = source.removeprefix("item: ").removeprefix("ability: ")
        handler = getattr(self, "on_" + kind.lstrip("-").replace("-", "_"), None)
        if handler is not None:
            handler(args, source, tags)

    def on_turn(self, args: list[str], *_: object) -> None:
        self.start_turn(int(args[0]))

    def on_switch(self, args: list[str], *_: object) -> None:
        match = IDENT.match(args[0])
        if match is None or match["slot"] is None:
            return
        species = species_of(args[1])
        self.species[(match["side"], match["name"])] = species
        self.field[match["side"]][match["slot"]] = {"species": species, "status": None}
        self.apply_condition(args[0], args[2])
        self.say(f"{self.labels[match['side']]} sent out {species}.")

    on_drag = on_switch

    def on_move(self, args: list[str], _source: str | None, tags: list[str]) -> None:
        target = args[2] if len(args) > 2 and args[2] and not args[2].startswith("[") else ""
        spread = any(t.startswith("[spread]") for t in tags)
        if target and target != args[0] and not spread:
            self.say(f"{self.who(args[0])} used {args[1]} on {self.who(target)}.")
        else:
            self.say(f"{self.who(args[0])} used {args[1]}.")

    def on_damage(self, args: list[str], source: str | None, _tags: list[str]) -> None:
        self.apply_condition(args[0], args[1])
        if args[1].endswith("fnt"):
            return
        cause = f" from {source}" if source else ""
        self.say(f"{self.who(args[0])} took damage{cause}, down to {self.percent(args[0])}%.")

    def on_heal(self, args: list[str], source: str | None, _tags: list[str]) -> None:
        self.apply_condition(args[0], args[1])
        cause = f" from {source}" if source else ""
        self.say(f"{self.who(args[0])} recovered{cause}, up to {self.percent(args[0])}%.")

    def on_faint(self, args: list[str], *_: object) -> None:
        self.apply_condition(args[0], "0 fnt")
        self.say(f"{self.who(args[0])} fainted.")

    def on_supereffective(self, args: list[str], *_: object) -> None:
        self.say(f"It was super effective on {self.who(args[0])}.")

    def on_resisted(self, args: list[str], *_: object) -> None:
        self.say(f"It was not very effective on {self.who(args[0])}.")

    def on_immune(self, args: list[str], *_: object) -> None:
        self.say(f"{self.who(args[0])} was not affected.")

    def on_crit(self, args: list[str], *_: object) -> None:
        self.say(f"A critical hit on {self.who(args[0])}.")

    def on_miss(self, args: list[str], *_: object) -> None:
        self.say(f"{self.who(args[0])} missed.")

    def on_fail(self, args: list[str], *_: object) -> None:
        self.say(f"{self.who(args[0])}'s move failed.")

    def on_singleturn(self, args: list[str], *_: object) -> None:
        if args[1].removeprefix("move: ") in ("Protect", "Detect", "Spiky Shield"):
            self.say(f"{self.who(args[0])} protected itself.")

    def on_activate(self, args: list[str], *_: object) -> None:
        effect = args[1] if len(args) > 1 else ""
        if effect.startswith("move: "):
            name = effect[6:]
            if name in ("Protect", "Detect", "Spiky Shield"):
                self.say(f"{self.who(args[0])} was protected by {name}.")
        elif effect.startswith(("ability: ", "item: ")):
            self.say(f"{self.who(args[0])}'s {effect.split(': ', 1)[1]} activated.")

    def on_zbroken(self, args: list[str], *_: object) -> None:
        self.say(f"The attack broke through {self.who(args[0])}'s protection.")

    def boost(self, args: list[str], words: dict[int, str], extreme: str) -> None:
        amount = int(args[2]) if len(args) > 2 and args[2].isdigit() else 1
        if amount == 0:
            return
        stat = STATS.get(args[1], args[1])
        self.say(f"{self.who(args[0])}'s {stat} {words.get(amount, extreme)}.")

    def on_boost(self, args: list[str], *_: object) -> None:
        self.boost(args, RISE, "rose drastically")

    def on_unboost(self, args: list[str], *_: object) -> None:
        self.boost(args, FALL, "fell severely")

    def on_ability(self, args: list[str], *_: object) -> None:
        self.say(f"{self.who(args[0])}'s {args[1]} activated.")

    def on_enditem(self, args: list[str], _source: str | None, tags: list[str]) -> None:
        if "[eat]" in tags:
            self.say(f"{self.who(args[0])} ate its {args[1]}.")
        else:
            self.say(f"{self.who(args[0])}'s {args[1]} was used up.")

    def on_status(self, args: list[str], *_: object) -> None:
        mon = self.slot(args[0])
        if mon is not None:
            mon["status"] = args[1]
        self.say(f"{self.who(args[0])} {STATUS.get(args[1], 'got ' + args[1])}.")

    def on_curestatus(self, args: list[str], *_: object) -> None:
        mon = self.slot(args[0])
        if mon is not None:
            mon["status"] = None

    def on_fieldstart(self, args: list[str], *_: object) -> None:
        self.say(f"{args[0].removeprefix('move: ')} covered the field.")

    def on_fieldend(self, args: list[str], *_: object) -> None:
        self.say(f"{args[0].removeprefix('move: ')} faded.")

    def on_cant(self, args: list[str], *_: object) -> None:
        reason = {"flinch": " because it flinched", "par": " because it is paralyzed"}
        self.say(f"{self.who(args[0])} could not move{reason.get(args[1], '')}.")

    def on_hitcount(self, args: list[str], *_: object) -> None:
        self.say(f"It hit {args[1]} times.")

    def on_player(self, args: list[str], *_: object) -> None:
        if len(args) > 1 and args[1]:
            self.players[args[1]] = args[0]

    def on_win(self, args: list[str], *_: object) -> None:
        side = self.players.get(args[0])
        self.say(f"{self.labels[side] if side else args[0]} won.")

    def on_tie(self, *_: object) -> None:
        self.say("The game ended in a tie.")


def public_lines(log: Iterable[str]) -> Iterable[str]:
    """Drop the public copy that follows each secret line after |split|."""
    skip = 0
    for line in log:
        if skip == 2:
            skip = 1
            yield line
            continue
        if skip == 1:
            skip = 0
            continue
        if line.startswith("|split|"):
            skip = 2
            continue
        yield line


def slot_choices(decision: dict[str, Any], names: Names) -> list[dict[str, Any]] | None:
    """What one side could pick for each active slot, and what it picked."""
    request = decision["request"]
    active = request.get("active")
    if not active or request.get("forceSwitch") or request.get("teamPreview"):
        return None
    team = request["side"]["pokemon"]
    picks = [p.strip() for p in decision["choice"].split(",")]
    slots = []
    for index, options in enumerate(active):
        mon = team[index]
        if parse_condition(mon["condition"])["fainted"]:
            continue
        moves = [
            {
                "name": names["moves"].get(m["id"], m.get("move", m["id"])),
                "pp": m.get("pp"),
                "maxpp": m.get("maxpp"),
                "disabled": bool(m.get("disabled")),
                "protect": m["id"] in PROTECTION_MOVE_IDS,
            }
            for m in options.get("moves", [])
        ]
        pick = picks[index].split() if index < len(picks) else ["pass"]
        chosen: dict[str, Any] = {"kind": pick[0] if pick else "pass"}
        if chosen["kind"] == "move" and len(pick) > 1 and pick[1].isdigit():
            chosen["index"] = int(pick[1]) - 1
            chosen["name"] = moves[chosen["index"]]["name"]
        elif chosen["kind"] == "switch" and len(pick) > 1 and pick[1].isdigit():
            chosen["species"] = species_of(team[int(pick[1]) - 1]["details"])
        slots.append(
            {
                "slot": "ab"[index],
                "species": species_of(mon["details"]),
                "moves": moves,
                "chosen": chosen,
            }
        )
    return slots


def roster(decision: dict[str, Any], names: Names) -> list[dict[str, Any]]:
    """A team sheet from the team-preview request."""
    members = []
    for mon in decision["request"]["side"]["pokemon"]:
        condition = parse_condition(mon["condition"])
        members.append(
            {
                "species": species_of(mon["details"]),
                "item": names["items"].get(mon.get("item", ""), mon.get("item", "")),
                "ability": names["abilities"].get(mon.get("ability", ""), mon.get("ability", "")),
                "moves": [names["moves"].get(m, m) for m in mon.get("moves", [])],
                "stats": {"hp": condition.get("maxhp", 0), **mon.get("stats", {})},
            }
        )
    return members


def build_battle(
    number: int,
    run: dict[str, Any],
    game: dict[str, Any],
    replay: dict[str, Any],
    names: Names,
) -> dict[str, Any]:
    candidate = game["candidate_role"]
    opponent = "p2" if candidate == "p1" else "p1"
    labels = {candidate: run["agent"].capitalize(), opponent: OPPONENT_LABEL}
    builder = FrameBuilder(labels)
    for line in public_lines(replay["log"]):
        builder.feed(line)
    builder.finish()

    rosters: dict[str, list[dict[str, Any]]] = {}
    for decision in replay["decisions"]:
        if decision["request"].get("teamPreview"):
            rosters[decision["side"]] = roster(decision, names)
            continue
        frame = next((f for f in builder.frames if f["turn"] == decision["turn"]), None)
        choices = slot_choices(decision, names)
        if frame is not None and choices is not None:
            frame.setdefault("choices", {})[decision["side"]] = choices

    return {
        "schema_version": SCHEMA_VERSION,
        "id": f"{number:04d}",
        "run": run["name"],
        "game_id": game["game_id"],
        "agent": run["agent"],
        "seed": run["seed"],
        "generation": run["generation"],
        "variant": game["variant"],
        "format_id": game["format_id"],
        "eval_seed": game["eval_seed"],
        "battle_seed": game["battle_seed"],
        "checkpoint": run["checkpoint"],
        "simulator_revision": run["simulator_revision"],
        "candidate": game["candidate"],
        "opponent": game["opponent"],
        "candidate_side": candidate,
        "labels": labels,
        "teams": {candidate: game["candidate_team"], opponent: game["opponent_team"]},
        "result": game["result"],
        "end_reason": game["end_reason"],
        "turns": game["turns"],
        "protect": {
            "uses": game["candidate_protect_uses"],
            "opportunities": game["candidate_protect_opportunities"],
            "depleted": game["protect_depleted"],
        },
        "rosters": rosters,
        "prelude": builder.prelude,
        "frames": builder.frames,
    }


def index_row(battle: dict[str, Any]) -> dict[str, Any]:
    keys = ("id", "run", "game_id", "agent", "seed", "generation", "variant", "result")
    row = {key: battle[key] for key in keys}
    side = battle["candidate_side"]
    other = "p2" if side == "p1" else "p1"
    row.update(
        {
            "end_reason": battle["end_reason"],
            "turns": battle["turns"],
            "protect_uses": battle["protect"]["uses"],
            "protect_opportunities": battle["protect"]["opportunities"],
            "protect_depleted": battle["protect"]["depleted"],
            "candidate_team": battle["teams"][side],
            "opponent_team": battle["teams"][other],
            "candidate_side": side,
        }
    )
    return row


def load_runs(runs_dir: Path) -> list[dict[str, Any]]:
    """Checkpoint evaluation runs in study order: agent, training seed, generation."""
    runs = []
    for path in runs_dir.rglob("results.json"):
        document = json.loads(path.read_text(encoding="utf-8"))
        name = document["summary"]["candidate_name"]
        match = CHECKPOINT_NAME.match(name)
        if match is None:
            continue
        runs.append(
            {
                "name": name,
                "agent": match["agent"],
                "seed": int(match["seed"]),
                "generation": int(match["gen"]),
                "checkpoint": Path(document["options"].get("checkpoint") or name).name,
                "simulator_revision": document["simulator_revision"],
                "spec": document["spec"],
                "dir": path.parent,
                "path": path,
                "games": document["games"],
            }
        )
    runs.sort(key=lambda r: (AGENT_ORDER.index(r["agent"]), r["seed"], r["generation"]))
    return runs


def read_replay(run: dict[str, Any], game: dict[str, Any]) -> dict[str, Any]:
    replay: dict[str, Any] = json.loads(gzip.decompress((run["dir"] / game["replay"]).read_bytes()))
    return replay


def collect_ids(runs: list[dict[str, Any]]) -> dict[str, set[str]]:
    ids: dict[str, set[str]] = {"moves": set(), "items": set(), "abilities": set()}
    for run in runs:
        for game in run["games"]:
            for decision in read_replay(run, game)["decisions"]:
                request = decision["request"]
                for mon in request.get("side", {}).get("pokemon", []):
                    ids["moves"].update(mon.get("moves", []))
                    ids["items"].update(filter(None, [mon.get("item")]))
                    ids["abilities"].update(filter(None, [mon.get("ability")]))
    return ids


def export_showcase(
    runs_dir: Path,
    output_dir: Path,
    names_for: Callable[[dict[str, set[str]]], Names],
) -> dict[str, Any]:
    """Write battles.json, battles/<id>.json.gz, teams.json, and recovery.json for the site."""
    runs = load_runs(runs_dir)
    names = names_for(collect_ids(runs))
    battles_dir = output_dir / "battles"
    battles_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    teams: dict[str, list[dict[str, Any]]] = {}
    number = 0
    for run in runs:
        for game in sorted(run["games"], key=lambda g: g["game_id"]):
            number += 1
            battle = build_battle(number, run, game, read_replay(run, game), names)
            for side, team_id in battle["teams"].items():
                if side in battle["rosters"]:
                    teams.setdefault(team_id, battle["rosters"][side])
            payload = json.dumps(battle, separators=(",", ":")).encode("utf-8")
            path = battles_dir / f"{battle['id']}.json.gz"
            path.write_bytes(gzip.compress(payload, mtime=0))
            rows.append(index_row(battle))

    meta = {
        "schema_version": SCHEMA_VERSION,
        "spec": sorted({r["spec"] for r in runs}),
        "simulator_revision": sorted({r["simulator_revision"] for r in runs}),
        "opponent": sorted({g["opponent"] for r in runs for g in r["games"]}),
        "eval_seed": sorted({g["eval_seed"] for r in runs for g in r["games"]}),
        "checkpoints": len(runs),
        "games": len(rows),
    }
    documents = {
        "battles.json": {**meta, "battles": rows},
        "teams.json": {"schema_version": SCHEMA_VERSION, "teams": teams},
        "recovery.json": summarize_recovery(r["path"] for r in runs),
    }
    for filename, document in documents.items():
        (output_dir / filename).write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")
    return meta
