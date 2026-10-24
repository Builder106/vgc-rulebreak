"""Unit tests for agent comparison harness across Protect rulesets."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from vgc_rulebreak.agents.base import BattleAgent
from vgc_rulebreak.cli import main
from vgc_rulebreak.evaluation import (
    AgentComparisonEntry,
    AgentComparisonReport,
    EvaluationBattleResult,
    HeadToHeadEntry,
    compare_study_agents,
)
from vgc_rulebreak.manifest import load_manifest
from vgc_rulebreak.spec import validate_spec

SPEC_PATH = Path("experiments/protect-pp.json")
MANIFEST_PATH = Path("experiments/teams/protect-pp.json")


def test_comparison_report_dataclass() -> None:
    entry = AgentComparisonEntry(
        agent_name="SourceAgent",
        variant="protect-16",
        total_matches=6,
        wins=5,
        losses=1,
        ties=0,
        win_rate=0.833,
        avg_turns=9.5,
        protect_uses_per_match=3.2,
        protect_depletion_rate=0.0,
        avg_duration_seconds=3.5,
    )
    h2h = HeadToHeadEntry(
        agent_a="SourceAgent",
        agent_b="NativeAgent",
        variant="protect-8",
        total_matches=6,
        a_wins=2,
        b_wins=4,
        ties=0,
        a_win_rate=0.333,
    )
    report = AgentComparisonReport(
        eval_seed=101,
        baseline_opponent="RandomBaseline",
        pairs_per_matchup=1,
        quick=True,
        entries=(entry,),
        head_to_head=(h2h,),
        findings={"source_transfer_loss": 0.25},
    )

    assert report.eval_seed == 101
    assert len(report.entries) == 1
    assert len(report.head_to_head) == 1
    assert report.findings["source_transfer_loss"] == 0.25


def test_compare_study_agents_mocked() -> None:
    spec = validate_spec(json.loads(SPEC_PATH.read_text(encoding="utf-8")))
    manifest = load_manifest(MANIFEST_PATH)

    call_count = 0

    def fake_battle(
        candidate_agent: BattleAgent,
        opponent_agent: BattleAgent,
        format_id: str,
        **_: object,
    ) -> EvaluationBattleResult:
        nonlocal call_count
        call_count += 1
        cand_won = call_count % 3 != 0
        depleted = (
            "Source" in candidate_agent.name
            and format_id == "gen9rulebreakprotect8"
        )
        return EvaluationBattleResult(
            winner=candidate_agent.name if cand_won else opponent_agent.name,
            turns=10,
            duration_seconds=2.0,
            candidate_decisions=10,
            opponent_decisions=10,
            candidate_protect_uses=3,
            opponent_protect_uses=2,
            protect_depleted=depleted,
            candidate_won=cand_won,
        )

    with patch("vgc_rulebreak.evaluation.run_evaluation_battle", side_effect=fake_battle):
        report = compare_study_agents(
            spec=spec,
            manifest=manifest,
            opponent_policy="RandomBaseline",
            eval_seed=101,
            pairs=1,
            quick=True,
        )

    assert len(report.entries) == 6  # 3 agents * 2 variants
    assert len(report.head_to_head) == 3  # 3 h2h pairings
    assert "source_transfer_loss" in report.findings
    assert "source_8pp_depletion_rate" in report.findings


def test_cli_compare_agents_parser(capsys: pytest.CaptureFixture[str]) -> None:
    # Test CLI invocation with mock
    fake_report = AgentComparisonReport(
        eval_seed=101,
        baseline_opponent="RandomBaseline",
        pairs_per_matchup=1,
        quick=True,
        entries=(),
        head_to_head=(),
        findings={"test": True},
    )
    with patch("vgc_rulebreak.evaluation.compare_study_agents", return_value=fake_report):
        code = main(["compare-agents", "--quick"])
        assert code == 0

    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["eval_seed"] == 101
    assert data["findings"]["test"] is True
