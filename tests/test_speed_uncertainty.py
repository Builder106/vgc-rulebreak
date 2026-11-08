"""Synthetic player evidence: support bounds, confounds and hidden-state isolation."""

import copy
import json
from pathlib import Path

import pytest

from vgc_rulebreak.cli import main
from vgc_rulebreak.speed_uncertainty import StatSystem, legal_speeds, report_speed_uncertainty


def observation(**changes: object) -> dict[str, object]:
    row: dict[str, object] = {
        "turn": 1,
        "own_speed": 72,
        "opponent_first": True,
        "own_priority": 0,
        "opponent_priority": 0,
        "trick_room": False,
        "own_tailwind": False,
        "opponent_tailwind": False,
        "speed_order_certified": True,
    }
    return row | changes


def evidence(*rows: dict[str, object], system: str = "ev") -> dict[str, object]:
    return {"base_speed": 47, "system": system, "observations": list(rows)}


@pytest.mark.parametrize("system,low,high", [("ev", 46, 108), ("sp", 60, 108)])
def test_legal_prior_and_no_evidence(system: StatSystem, low: int, high: int) -> None:
    report = report_speed_uncertainty(evidence(system=system))
    assert report["minimum"] == low
    assert report["maximum"] == high
    assert report["remaining_count"] == report["prior_count"]
    assert report["observations_used"] == 0
    assert report["possible_speeds"] == list(legal_speeds(47, system))


def test_bounds_and_tie_survive_both_orders_and_repeated_evidence() -> None:
    rows = [observation(), observation(turn=2, own_speed=80, opponent_first=False)]
    report = report_speed_uncertainty(evidence(*rows))
    assert report["possible_speeds"] == list(range(72, 81))
    rows += [observation(turn=3, opponent_first=False)] * 10
    report = report_speed_uncertainty(evidence(*rows))
    assert report["possible_speeds"] == [72]
    assert report["status"] == "consistent"


@pytest.mark.parametrize("trick_room", [False, True])
@pytest.mark.parametrize(
    "own_tailwind,opponent_tailwind", [(False, False), (True, False), (False, True)]
)
def test_every_possible_true_speed_is_retained_for_its_observed_order(
    trick_room: bool, own_tailwind: bool, opponent_tailwind: bool
) -> None:
    # Exhaustive support soundness under the supported order model, including ties.
    for actual in legal_speeds(47, "ev"):
        own = 72 * (2 if own_tailwind else 1)
        opponent = actual * (2 if opponent_tailwind else 1)
        for first in (False, True):
            if opponent != own and first != ((opponent > own) != trick_room):
                continue
            report = report_speed_uncertainty(
                evidence(
                    observation(
                        opponent_first=first,
                        trick_room=trick_room,
                        own_tailwind=own_tailwind,
                        opponent_tailwind=opponent_tailwind,
                    )
                )
            )
            possible = report["possible_speeds"]
            assert isinstance(possible, list)
            assert actual in possible


@pytest.mark.parametrize(
    "changes",
    [
        {"own_priority": -6},
        {"opponent_priority": 4},
        {"speed_order_certified": False},
    ],
)
def test_confounded_orders_do_not_narrow(changes: dict[str, object]) -> None:
    report = report_speed_uncertainty(evidence(observation(**changes)))
    assert report["remaining_count"] == report["prior_count"]
    assert report["observations_used"] == 0
    assert report["observations_skipped"] == 1


def test_inconsistency_is_explicit_instead_of_silent_reset() -> None:
    report = report_speed_uncertainty(
        evidence(
            observation(own_speed=100),
            observation(turn=2, own_speed=60, opponent_first=False),
        )
    )
    assert report["status"] == "inconsistent_evidence"
    assert report["possible_speeds"] == []
    assert report["minimum"] is None
    assert report["maximum"] is None


@pytest.mark.parametrize("private_field", ["opponent_speed", "seed", "requests", "initial", "ivs"])
@pytest.mark.parametrize("nested", [False, True])
def test_private_state_is_rejected_at_every_boundary(private_field: str, nested: bool) -> None:
    row = observation()
    data = evidence(row)
    (row if nested else data)[private_field] = {"hidden": 67}
    with pytest.raises(ValueError, match="public fields"):
        report_speed_uncertainty(data)


def test_same_observations_have_identical_report_for_distinct_hidden_builds() -> None:
    # An audit harness may hold hidden state, but only this projection crosses the API.
    public = evidence(observation())
    audits = [{"public": copy.deepcopy(public), "opponent_speed": speed} for speed in (72, 100)]
    assert report_speed_uncertainty(audits[0]["public"]) == report_speed_uncertainty(
        audits[1]["public"]
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"own_speed": True},
        {"own_speed": 0},
        {"turn": -1},
        {"opponent_first": "false"},
        {"own_priority": 6},
        {"speed_order_certified": None},
    ],
)
def test_invalid_observations_fail_closed(changes: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        report_speed_uncertainty(evidence(observation(**changes)))


@pytest.mark.parametrize(
    "value", [None, [], {}, {"base_speed": 47, "system": "ev", "observations": {}}]
)
def test_invalid_input(value: object) -> None:
    with pytest.raises(ValueError):
        report_speed_uncertainty(value)


@pytest.mark.parametrize("base,system", [(True, "ev"), (0, "ev"), (256, "ev"), (47, "unknown")])
def test_invalid_prior(base: int, system: str) -> None:
    with pytest.raises(ValueError):
        report_speed_uncertainty({"base_speed": base, "system": system, "observations": []})


def test_cli_reports_and_rejects_raw_private_records(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "public.json"
    path.write_text(json.dumps(evidence(observation())), encoding="utf-8")
    assert main(["report-speed-uncertainty", str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["minimum"] == 72
    path.write_text('{"initial": {"opponent_speed": 67}}', encoding="utf-8")
    assert main(["report-speed-uncertainty", str(path)]) == 2
    assert "public fields" in capsys.readouterr().err
    path.write_text("{", encoding="utf-8")
    assert main(["report-speed-uncertainty", str(path)]) == 2
