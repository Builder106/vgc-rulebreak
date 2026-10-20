"""Validate and load Open Team Sheet (OTS) battle team manifests."""

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TeamMember:
    species: str
    item: str
    ability: str
    moves: tuple[str, ...]
    nature: str
    evs: dict[str, int]
    tera_type: str


@dataclass(frozen=True)
class BattleTeam:
    id: str
    family: str
    split: str
    pokemon: tuple[TeamMember, ...]
    packed: str


@dataclass(frozen=True)
class TeamManifest:
    schema_version: int
    name: str
    base_format: str
    description: str
    splits: dict[str, tuple[str, ...]]
    teams: dict[str, BattleTeam]


def _object(value: object, label: str, keys: set[str]) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f"{label} must contain exactly these fields: {', '.join(sorted(keys))}")
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValueError(f"{label} field names must be strings")
        result[key] = item
    return result


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")
    return value.strip()


def validate_manifest(data: object) -> TeamManifest:
    """Validate a parsed team manifest dictionary."""
    doc = _object(
        data,
        "team_manifest",
        {"schema_version", "name", "base_format", "description", "splits", "teams"},
    )
    if type(doc["schema_version"]) is not int or doc["schema_version"] != 1:
        raise ValueError("schema_version must be 1")

    name = _text(doc["name"], "name")
    base_format = _text(doc["base_format"], "base_format")
    description = _text(doc["description"], "description")

    raw_splits = _object(doc["splits"], "splits", {"training", "validation", "test"})
    splits: dict[str, tuple[str, ...]] = {}
    all_split_ids: set[str] = set()

    for split_name, ids_obj in raw_splits.items():
        if not isinstance(ids_obj, list) or not ids_obj:
            raise ValueError(f"splits.{split_name} must be a nonempty list of team IDs")
        team_ids: list[str] = []
        for item in ids_obj:
            t_id = _text(item, f"splits.{split_name} ID")
            if t_id in all_split_ids:
                raise ValueError(f"duplicate team ID across splits: {t_id}")
            all_split_ids.add(t_id)
            team_ids.append(t_id)
        splits[split_name] = tuple(team_ids)

    raw_teams = doc["teams"]
    if not isinstance(raw_teams, dict):
        raise ValueError("teams must be a dictionary mapping team IDs to team data")

    if set(raw_teams.keys()) != all_split_ids:
        missing = all_split_ids - set(raw_teams.keys())
        extra = set(raw_teams.keys()) - all_split_ids
        err_parts: list[str] = []
        if missing:
            err_parts.append(f"missing definitions for: {', '.join(sorted(missing))}")
        if extra:
            err_parts.append(f"extra teams not declared in splits: {', '.join(sorted(extra))}")
        raise ValueError("; ".join(err_parts))

    teams: dict[str, BattleTeam] = {}
    for team_id, team_obj in raw_teams.items():
        t_data = _object(
            team_obj,
            f"team {team_id}",
            {"family", "split", "pokemon", "packed"},
        )
        family = _text(t_data["family"], f"team {team_id}.family")
        split = _text(t_data["split"], f"team {team_id}.split")
        if split not in {"training", "validation", "test"}:
            raise ValueError(f"team {team_id}.split must be training, validation, or test")
        if team_id not in splits[split]:
            raise ValueError(f"team {team_id} split declared as {split} but listed elsewhere")

        packed = _text(t_data["packed"], f"team {team_id}.packed")

        raw_pokes = t_data["pokemon"]
        if not isinstance(raw_pokes, list) or len(raw_pokes) not in {4, 6}:
            raise ValueError(f"team {team_id}.pokemon must contain exactly 4 or 6 members")

        members: list[TeamMember] = []
        for p_idx, p_obj in enumerate(raw_pokes):
            if not isinstance(p_obj, dict):
                raise ValueError(f"team {team_id}.pokemon[{p_idx}] must be a dict")
            required_keys = {"species", "item", "ability", "moves", "nature", "evs", "teraType"}
            if not required_keys.issubset(set(p_obj.keys())):
                missing_keys = required_keys - set(p_obj.keys())
                raise ValueError(
                    f"team {team_id}.pokemon[{p_idx}] missing required fields: "
                    f"{', '.join(sorted(missing_keys))}"
                )
            species = _text(p_obj["species"], f"pokemon[{p_idx}].species")
            item = str(p_obj["item"])
            ability = _text(p_obj["ability"], f"pokemon[{p_idx}].ability")
            nature = _text(p_obj["nature"], f"pokemon[{p_idx}].nature")
            tera_type = _text(p_obj["teraType"], f"pokemon[{p_idx}].teraType")

            raw_moves = p_obj["moves"]
            if not isinstance(raw_moves, list) or not (1 <= len(raw_moves) <= 4):
                raise ValueError(f"pokemon[{p_idx}].moves must contain 1 to 4 moves")
            moves = tuple(_text(m, f"pokemon[{p_idx}].moves") for m in raw_moves)

            raw_evs = p_obj["evs"]
            if not isinstance(raw_evs, dict):
                raise ValueError(f"pokemon[{p_idx}].evs must be a dict")
            evs = {str(k): int(v) for k, v in raw_evs.items()}

            members.append(
                TeamMember(
                    species=species,
                    item=item,
                    ability=ability,
                    moves=moves,
                    nature=nature,
                    evs=evs,
                    tera_type=tera_type,
                )
            )

        teams[team_id] = BattleTeam(
            id=team_id,
            family=family,
            split=split,
            pokemon=tuple(members),
            packed=packed,
        )

    return TeamManifest(
        schema_version=1,
        name=name,
        base_format=base_format,
        description=description,
        splits=splits,
        teams=teams,
    )


def load_manifest(path: Path | str) -> TeamManifest:
    """Load and validate a JSON team manifest file."""
    p = Path(path)
    content = p.read_text(encoding="utf-8")
    raw = json.loads(content)
    return validate_manifest(raw)
