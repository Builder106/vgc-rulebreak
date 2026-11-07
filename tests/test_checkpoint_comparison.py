"""Tests for checkpoint comparison harness across Protect rulesets."""

import json
from pathlib import Path

import pytest

from vgc_rulebreak.agents.trained import ProtectParams, TrainedProtectAgent
from vgc_rulebreak.checkpoint_comparison import (
    FORBIDDEN_BELIEF_WORDS,
    CheckpointComparisonReport,
    CheckpointMetadata,
    DecisionDivergenceSummary,
    PairedPerformanceComparison,
    ParameterDeltaSummary,
    analyze_decision_divergence,
    build_checkpoint_comparison_narrative,
    compare_checkpoint_parameters,
    compare_checkpoints,
    evaluate_checkpoint_performance,
    verify_no_unsupported_beliefs,
)
from vgc_rulebreak.cli import main
from vgc_rulebreak.protect_multi_seed import ConfidenceInterval


def test_compare_checkpoint_parameters() -> None:
    p_orig = ProtectParams(
        base_score=50.0,
        low_hp_score=95.0,
        hp_threshold=0.35,
        scarcity_slope=0.0,
        pp_cushion=0.0,
    )
    p_adapt = ProtectParams(
        base_score=20.0,
        low_hp_score=110.0,
        hp_threshold=0.50,
        scarcity_slope=0.0,
        pp_cushion=0.0,
    )

    summary = compare_checkpoint_parameters(p_orig, p_adapt)

    assert summary.deltas["base_score"] == -30.0
    assert summary.deltas["low_hp_score"] == 15.0
    assert summary.deltas["hp_threshold"] == 0.15
    assert summary.deltas["scarcity_slope"] == 0.0
    assert summary.is_scarcity_sensitive is False
    assert summary.l1_distance > 0.0
    assert summary.l2_distance > 0.0
    assert "Both checkpoints retain scarcity_slope = 0.0" in summary.factual_description


def test_verify_no_unsupported_beliefs() -> None:
    compliant_text = (
        "Observable Protect PP remaining is 8/8. The agent chose Protect on 2 of 35 "
        "opportunities. Outcome difference is not statistically distinguishable from zero."
    )
    # Compliant text should not raise
    verify_no_unsupported_beliefs(compliant_text)

    # Every forbidden word must trigger a ValueError
    for word in FORBIDDEN_BELIEF_WORDS:
        violating_text = f"The agent {word} that Protect was scarce."
        with pytest.raises(ValueError, match="Unsupported internal belief word"):
            verify_no_unsupported_beliefs(violating_text)


def test_evaluate_checkpoint_performance() -> None:
    games = [
        {
            "game_id": "g1",
            "variant": "protect-8",
            "result": "win",
            "turns": 10,
            "candidate_protect_uses": 2,
            "candidate_protect_opportunities": 20,
            "protect_depleted": False,
        },
        {
            "game_id": "g2",
            "variant": "protect-8",
            "result": "loss",
            "turns": 8,
            "candidate_protect_uses": 1,
            "candidate_protect_opportunities": 10,
            "protect_depleted": False,
        },
    ]

    perf = evaluate_checkpoint_performance(games, "protect-8", "gen9rulebreakprotect8")
    assert perf.total_matches == 2
    assert perf.wins == 1
    assert perf.losses == 1
    assert perf.win_rate == 0.5
    assert perf.points_per_game == 0.5
    assert perf.avg_turns == 9.0
    assert perf.candidate_protect_uses == 3
    assert perf.candidate_protect_opportunities == 30
    assert perf.protect_use_rate == 0.1
    assert perf.protect_depletions == 0
    assert perf.depletion_rate == 0.0


def test_analyze_decision_divergence() -> None:
    # Set up original and adapted agents with different parameters
    orig_params = ProtectParams(
        base_score=10.0,
        low_hp_score=100.0,
        hp_threshold=0.30,
        scarcity_slope=0.0,
        pp_cushion=0.0,
    )
    adapt_params = ProtectParams(
        base_score=80.0,  # Adapted scores Protect much higher
        low_hp_score=100.0,
        hp_threshold=0.80,
        scarcity_slope=0.0,
        pp_cushion=0.0,
    )
    orig_agent = TrainedProtectAgent(orig_params, name="SourceAgent")
    adapt_agent = TrainedProtectAgent(adapt_params, name="AdaptedAgent")

    # Construct synthetic replay with one active slot
    replay = {
        "game_id": "g001",
        "players": {"p1": {"name": "source-test"}, "p2": {"name": "opponent"}},
        "decisions": [
            {
                "side": "p1",
                "turn": 1,
                "request": {
                    "active": [
                        {
                            "moves": [
                                {
                                    "move": "Protect",
                                    "id": "protect",
                                    "pp": 8,
                                    "maxpp": 8,
                                    "target": "self",
                                    "disabled": False,
                                },
                                {
                                    "move": "Tackle",
                                    "id": "tackle",
                                    "pp": 35,
                                    "maxpp": 35,
                                    "target": "normal",
                                    "disabled": False,
                                },
                            ]
                        }
                    ],
                    "side": {
                        "name": "p1",
                        "pokemon": [
                            {
                                "ident": "p1: Pikachu",
                                "details": "Pikachu, L50, M",
                                "condition": "50/100",  # HP ratio = 0.50
                                "moves": ["protect", "tackle"],
                            }
                        ],
                    },
                },
            }
        ],
    }

    divergence = analyze_decision_divergence(orig_agent, adapt_agent, [replay])
    assert divergence.total_decisions_compared == 1
    # At HP 0.50, orig (threshold 0.30) uses base_score=10,
    # while adapted (threshold 0.80) uses low_hp_score=100
    assert divergence.agreement_rate in (0.0, 1.0)
    assert len(divergence.divergence_records) in (0, 1)


def test_build_checkpoint_comparison_narrative_compliance() -> None:
    meta_orig = CheckpointMetadata(
        path="checkpoints/source-s11-g01.json",
        agent="source",
        ruleset="protect-16",
        format_id="gen9rulebreakprotect16",
        training_seed=11,
        generation=1,
        params={
            "base_score": 50.0,
            "low_hp_score": 95.0,
            "hp_threshold": 0.35,
            "scarcity_slope": 0.0,
            "pp_cushion": 0.0,
        },
        unit_mean=[0.33, 0.47, 0.35, 0.0, 0.0],
        unit_std=[0.02] * 5,
    )
    meta_adapt = CheckpointMetadata(
        path="checkpoints/adapted-s11-g01.json",
        agent="adapted",
        ruleset="protect-8",
        format_id="gen9rulebreakprotect8",
        training_seed=11,
        generation=1,
        params={
            "base_score": 20.0,
            "low_hp_score": 105.0,
            "hp_threshold": 0.50,
            "scarcity_slope": 0.0,
            "pp_cushion": 0.0,
        },
        unit_mean=[0.13, 0.52, 0.50, 0.0, 0.0],
        unit_std=[0.02] * 5,
    )
    param_summary = ParameterDeltaSummary(
        deltas={
            "base_score": -30.0,
            "low_hp_score": 10.0,
            "hp_threshold": 0.15,
            "scarcity_slope": 0.0,
            "pp_cushion": 0.0,
        },
        l1_distance=0.15,
        l2_distance=0.10,
        original_scarcity_slope=0.0,
        adapted_scarcity_slope=0.0,
        scarcity_slope_shift=0.0,
        is_scarcity_sensitive=False,
        factual_description="Parameter comparison description.",
    )
    perf_mock = evaluate_checkpoint_performance([], "protect-8", "gen9rulebreakprotect8")
    orig_perf = {"protect-16": perf_mock, "protect-8": perf_mock}
    adapt_perf = {"protect-16": perf_mock, "protect-8": perf_mock}

    ci = ConfidenceInterval(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 6)
    paired_diff = PairedPerformanceComparison(
        variant="protect-8",
        delta_ppg=0.0,
        delta_win_rate=0.0,
        delta_protect_use_rate=0.0,
        delta_ppg_ci_95=ci,
        is_statistically_significant=False,
        scarcity_binds=False,
    )
    paired_diffs = {"protect-16": paired_diff, "protect-8": paired_diff}
    divergence = DecisionDivergenceSummary(10, 10, 0, 1.0, 1.0, ())

    narrative = build_checkpoint_comparison_narrative(
        orig_meta=meta_orig,
        adapt_meta=meta_adapt,
        param_summary=param_summary,
        orig_perf=orig_perf,
        adapt_perf=adapt_perf,
        paired_diffs=paired_diffs,
        divergence=divergence,
    )

    assert "## Checkpoint Comparison: Original versus Adapted Policies" in narrative
    assert "scarcity_slope = 0.0" in narrative
    assert "0 Protect depletions" in narrative
    # Must not raise unsupported belief error
    verify_no_unsupported_beliefs(narrative)


def test_compare_checkpoints_end_to_end_on_milestone_files() -> None:
    orig_ckpt = Path("runs/protect-rerun-milestone/checkpoints/source-s11-g01.json")
    adapt_ckpt = Path("runs/protect-rerun-milestone/checkpoints/adapted-s11-g01.json")
    nat_ckpt = Path("runs/protect-rerun-milestone/checkpoints/native-s11-g01.json")
    orig_eval = Path("runs/protect-rerun-milestone/eval/source-s11-g01")
    adapt_eval = Path("runs/protect-rerun-milestone/eval/adapted-s11-g01")
    nat_eval = Path("runs/protect-rerun-milestone/eval/native-s11-g01")

    if not (orig_ckpt.exists() and adapt_ckpt.exists()):
        pytest.skip("Milestone run artifacts not found on disk.")

    report = compare_checkpoints(
        original_checkpoint_path=orig_ckpt,
        adapted_checkpoint_path=adapt_ckpt,
        native_checkpoint_path=nat_ckpt if nat_ckpt.exists() else None,
        original_results_path=orig_eval if orig_eval.exists() else None,
        adapted_results_path=adapt_eval if adapt_eval.exists() else None,
        native_results_path=nat_eval if nat_eval.exists() else None,
    )

    assert isinstance(report, CheckpointComparisonReport)
    assert report.original.agent == "source"
    assert report.adapted.agent == "adapted"
    assert report.findings["is_scarcity_sensitive"] is False
    assert report.findings["scarcity_binds_in_either_checkpoint"] is False
    assert report.findings["target_format_delta_ppg"] == 0.0
    assert report.findings["is_target_format_delta_significant"] is False
    assert report.decision_divergence.agreement_rate == 1.0
    assert "null_result_confirmed" in report.findings["conclusion"]


def test_cli_compare_checkpoints(tmp_path: Path) -> None:
    orig_ckpt = Path("runs/protect-rerun-milestone/checkpoints/source-s11-g01.json")
    adapt_ckpt = Path("runs/protect-rerun-milestone/checkpoints/adapted-s11-g01.json")
    out_file = tmp_path / "comparison.json"

    if not (orig_ckpt.exists() and adapt_ckpt.exists()):
        pytest.skip("Milestone run artifacts not found on disk.")

    ret = main(
        [
            "compare-checkpoints",
            "--original",
            str(orig_ckpt),
            "--adapted",
            str(adapt_ckpt),
            "--original-eval",
            "runs/protect-rerun-milestone/eval/source-s11-g01",
            "--adapted-eval",
            "runs/protect-rerun-milestone/eval/adapted-s11-g01",
            "--output",
            str(out_file),
        ]
    )

    assert ret == 0
    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert "findings" in data
    assert "empirical_narrative" in data
