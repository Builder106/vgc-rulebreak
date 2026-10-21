"""Validate the first Protect study before simulator work begins."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class EvaluationSpec:
    test_teams: tuple[str, ...]
    opponent_policies: tuple[str, ...]
    evaluation_seeds: tuple[int, ...]


@dataclass(frozen=True)
class ExperimentSpec:
    name: str
    simulator_revision: str
    information_mode: str
    training_seeds: tuple[int, ...]
    variants: dict[str, int]
    pending_gates: tuple[str, ...]
    evaluation: EvaluationSpec | None = None


def _object(
    value: object,
    label: str,
    required_keys: set[str],
    optional_keys: set[str] | None = None,
) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a dictionary")
    actual_keys = set(value)
    allowed_keys = required_keys | (optional_keys or set())
    if not required_keys.issubset(actual_keys) or not actual_keys.issubset(allowed_keys):
        raise ValueError(
            f"{label} must contain exactly these fields: {', '.join(sorted(required_keys))}"
        )
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValueError(f"{label} field names must be strings")
        result[key] = item
    return result


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")
    return value


def validate_spec(value: object) -> ExperimentSpec:
    document = _object(
        value,
        "experiment",
        {
            "schema_version",
            "name",
            "question",
            "simulator_revision",
            "base_format",
            "information_mode",
            "training_seeds",
            "variants",
            "readiness",
        },
        optional_keys={"evaluation"},
    )
    if type(document["schema_version"]) is not int or document["schema_version"] != 1:
        raise ValueError("schema_version must be 1")
    name = _text(document["name"], "name")
    _text(document["question"], "question")
    _text(document["base_format"], "base_format")
    revision = _text(document["simulator_revision"], "simulator_revision")
    if re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise ValueError("simulator_revision must be a full lowercase Git commit ID")
    information = _text(document["information_mode"], "information_mode")
    if information not in {"open", "closed"}:
        raise ValueError("information_mode must be open or closed")

    seeds = document["training_seeds"]
    if not isinstance(seeds, list) or len(seeds) < 3:
        raise ValueError("training_seeds must contain at least three independent seeds")
    checked_seeds: list[int] = []
    for seed in seeds:
        if type(seed) is not int or seed < 0:
            raise ValueError("training_seeds must contain nonnegative integers")
        checked_seeds.append(seed)
    if len(set(checked_seeds)) != len(checked_seeds):
        raise ValueError("training_seeds must be unique")

    variants = document["variants"]
    if not isinstance(variants, list) or len(variants) != 2:
        raise ValueError("the Protect study must contain exactly two variants")
    checked_variants: dict[str, int] = {}
    for variant in variants:
        item = _object(variant, "variant", {"name", "rules"})
        variant_name = _text(item["name"], "variant.name")
        if variant_name in checked_variants:
            raise ValueError("variant names must be unique")
        rules = _object(item["rules"], "variant.rules", {"protect_max_pp"})
        pp = rules["protect_max_pp"]
        if type(pp) is not int or pp not in {8, 16}:
            raise ValueError("protect_max_pp must be 8 or 16")
        checked_variants[variant_name] = pp
    if set(checked_variants.values()) != {8, 16}:
        raise ValueError("the two variants must compare 16 and 8 maximum Protect PP")

    readiness = _object(
        document["readiness"],
        "readiness",
        {"mechanics_verified", "team_manifest", "pairs_per_matchup", "compute_budget_seconds"},
    )
    if type(readiness["mechanics_verified"]) is not bool:
        raise ValueError("mechanics_verified must be a boolean")
    manifest = readiness["team_manifest"]
    if manifest is not None:
        _text(manifest, "team_manifest")
    for field in ("pairs_per_matchup", "compute_budget_seconds"):
        number = readiness[field]
        if number is not None and (type(number) is not int or number <= 0):
            raise ValueError(f"{field} must be a positive integer or null")
    pending = tuple(key for key, item in readiness.items() if item is None or item is False)

    evaluation: EvaluationSpec | None = None
    if "evaluation" in document:
        eval_doc = _object(
            document["evaluation"],
            "evaluation",
            {"test_teams", "opponent_policies", "evaluation_seeds"},
        )
        raw_test_teams = eval_doc["test_teams"]
        if not isinstance(raw_test_teams, list) or len(raw_test_teams) == 0:
            raise ValueError("evaluation.test_teams must be a nonempty list of team names")
        checked_test_teams: list[str] = []
        for item in raw_test_teams:
            checked_test_teams.append(_text(item, "evaluation.test_teams"))
        if len(set(checked_test_teams)) != len(checked_test_teams):
            raise ValueError("evaluation.test_teams must contain unique team names")

        raw_opponents = eval_doc["opponent_policies"]
        if not isinstance(raw_opponents, list) or len(raw_opponents) == 0:
            raise ValueError("evaluation.opponent_policies must be a nonempty list")
        allowed_policies = {"HeuristicBaseline", "RandomBaseline"}
        checked_opponents: list[str] = []
        for item in raw_opponents:
            policy_name = _text(item, "evaluation.opponent_policies")
            if policy_name not in allowed_policies:
                raise ValueError(
                    f"unrecognized opponent policy: {policy_name}; "
                    f"allowed: {sorted(allowed_policies)}"
                )
            checked_opponents.append(policy_name)
        if len(set(checked_opponents)) != len(checked_opponents):
            raise ValueError("evaluation.opponent_policies must contain unique policies")

        raw_eval_seeds = eval_doc["evaluation_seeds"]
        if not isinstance(raw_eval_seeds, list) or len(raw_eval_seeds) < 3:
            raise ValueError(
                "evaluation.evaluation_seeds must contain at least three independent seeds"
            )
        checked_eval_seeds: list[int] = []
        for s in raw_eval_seeds:
            if type(s) is not int or s < 0:
                raise ValueError("evaluation.evaluation_seeds must contain nonnegative integers")
            checked_eval_seeds.append(s)
        if len(set(checked_eval_seeds)) != len(checked_eval_seeds):
            raise ValueError("evaluation.evaluation_seeds must be unique")

        if not set(checked_eval_seeds).isdisjoint(set(checked_seeds)):
            raise ValueError("evaluation.evaluation_seeds must be disjoint from training_seeds")

        evaluation = EvaluationSpec(
            test_teams=tuple(checked_test_teams),
            opponent_policies=tuple(checked_opponents),
            evaluation_seeds=tuple(checked_eval_seeds),
        )

    return ExperimentSpec(
        name,
        revision,
        information,
        tuple(checked_seeds),
        checked_variants,
        pending,
        evaluation,
    )
