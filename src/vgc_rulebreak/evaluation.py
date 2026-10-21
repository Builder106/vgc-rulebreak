"""Evaluation harness for frozen test teams, opponent policies, and seeds."""

import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from vgc_rulebreak.agents.base import BattleAgent
from vgc_rulebreak.agents.heuristic import HeuristicAgent
from vgc_rulebreak.agents.random import RandomAgent
from vgc_rulebreak.manifest import TeamManifest
from vgc_rulebreak.pilot import _check_protect_depleted, _count_protect_choices
from vgc_rulebreak.simulator.battle import BattleSession
from vgc_rulebreak.simulator.process import ShowdownProcess
from vgc_rulebreak.spec import ExperimentSpec

FROZEN_OPPONENT_POLICIES: tuple[str, ...] = ("HeuristicBaseline", "RandomBaseline")

FORMAT_BY_PP: dict[int, str] = {
    16: "gen9doublescustomgame",
    8: "gen9championsdoublescustomgame",
}


@dataclass(frozen=True)
class FrozenEvaluationConfig:
    test_teams: tuple[str, ...]
    opponent_policies: tuple[str, ...]
    evaluation_seeds: tuple[int, ...]
    pairs_per_matchup: int


@dataclass(frozen=True)
class EvaluationBattleResult:
    winner: str | None
    turns: int
    duration_seconds: float
    candidate_decisions: int
    opponent_decisions: int
    candidate_protect_uses: int
    opponent_protect_uses: int
    protect_depleted: bool
    candidate_won: bool


@dataclass(frozen=True)
class MatchupEvaluationSummary:
    variant: str
    eval_seed: int
    opponent_policy: str
    team_candidate: str
    team_opponent: str
    total_matches: int
    candidate_wins: int
    opponent_wins: int
    ties: int
    win_rate: float
    avg_turns: float
    candidate_protect_uses: int
    opponent_protect_uses: int
    protect_depleted_matches: int


@dataclass(frozen=True)
class EvaluationSummary:
    candidate_name: str
    variants: tuple[str, ...]
    eval_seeds: tuple[int, ...]
    opponent_policies: tuple[str, ...]
    test_teams: tuple[str, ...]
    total_matches: int
    candidate_wins: int
    opponent_wins: int
    ties: int
    overall_win_rate: float
    avg_turns: float
    total_duration_seconds: float
    decisions_per_second: float
    matchup_summaries: tuple[MatchupEvaluationSummary, ...]


def create_opponent_agent(policy_name: str, seed: int | None = None) -> BattleAgent:
    """Instantiate a frozen reference opponent baseline agent."""
    if policy_name == "HeuristicBaseline":
        return HeuristicAgent("HeuristicBaseline")
    elif policy_name == "RandomBaseline":
        return RandomAgent("RandomBaseline", seed=seed)
    else:
        raise ValueError(
            f"Unrecognized opponent policy: '{policy_name}'; "
            f"allowed policies are: {sorted(FROZEN_OPPONENT_POLICIES)}"
        )


def create_candidate_agent(
    agent_or_type: BattleAgent | str, seed: int | None = None
) -> BattleAgent:
    """Obtain or instantiate a candidate battle agent."""
    if isinstance(agent_or_type, BattleAgent):
        return agent_or_type
    if agent_or_type == "heuristic":
        return HeuristicAgent("HeuristicCandidate")
    if agent_or_type == "random":
        return RandomAgent("RandomCandidate", seed=seed)
    raise ValueError(f"Unknown candidate agent type: {agent_or_type}")


def verify_frozen_evaluation(spec: ExperimentSpec, manifest: TeamManifest) -> None:
    """Verify that the evaluation configuration strictly respects test split isolation."""
    if spec.evaluation is None:
        raise ValueError("Experiment specification is missing evaluation configuration")

    test_split = manifest.splits.get("test", ())
    training_split = manifest.splits.get("training", ())
    val_split = manifest.splits.get("validation", ())

    for team_id in spec.evaluation.test_teams:
        if team_id not in manifest.teams:
            raise ValueError(f"Evaluation test team '{team_id}' not found in team manifest")
        if team_id not in test_split:
            raise ValueError(
                f"Evaluation test team '{team_id}' is declared in split "
                f"'{manifest.teams[team_id].split}', expected 'test'"
            )
        if team_id in training_split:
            raise ValueError(
                f"Contamination error: test team '{team_id}' is present in training split"
            )
        if team_id in val_split:
            raise ValueError(
                f"Contamination error: test team '{team_id}' is present in validation split"
            )

    for policy in spec.evaluation.opponent_policies:
        if policy not in FROZEN_OPPONENT_POLICIES:
            raise ValueError(
                f"Opponent policy '{policy}' is not recognized in FROZEN_OPPONENT_POLICIES"
            )

    if len(spec.evaluation.evaluation_seeds) < 3:
        raise ValueError("Evaluation configuration must specify at least 3 evaluation seeds")

    if not set(spec.evaluation.evaluation_seeds).isdisjoint(set(spec.training_seeds)):
        raise ValueError("evaluation_seeds must be strictly disjoint from training_seeds")


def build_test_matchups(
    manifest: TeamManifest, test_teams: Sequence[str]
) -> list[tuple[str, str, str, str]]:
    """Build unique test team pairings (both mirror and cross-matchups)."""
    matchups: list[tuple[str, str, str, str]] = []
    sorted_teams = sorted(test_teams)
    for i, t1 in enumerate(sorted_teams):
        for t2 in sorted_teams[i:]:
            matchups.append((t1, manifest.teams[t1].packed, t2, manifest.teams[t2].packed))
    return matchups


def make_eval_battle_seed(
    eval_seed: int,
    variant_idx: int,
    opponent_idx: int,
    matchup_idx: int,
    pair_idx: int,
    game_idx: int,
) -> tuple[int, int, int, int]:
    """Derive a deterministic 4-tuple Showdown PRNG seed."""
    base = (
        (eval_seed * 100_000)
        + (variant_idx * 10_000)
        + (opponent_idx * 1_000)
        + (matchup_idx * 100)
        + (pair_idx * 10)
        + game_idx
    )
    return (
        (base + 1) & 0xFFFF,
        (base + 2) & 0xFFFF,
        (base + 3) & 0xFFFF,
        (base + 4) & 0xFFFF,
    )


def get_evaluation_plan(
    spec: ExperimentSpec,
    manifest: TeamManifest,
    pairs_override: int | None = None,
) -> dict[str, object]:
    """Compile a structured preview of the frozen evaluation plan."""
    verify_frozen_evaluation(spec, manifest)
    assert spec.evaluation is not None

    matchups = build_test_matchups(manifest, spec.evaluation.test_teams)
    matchup_pairs = [[m[0], m[2]] for m in matchups]

    pairs = pairs_override or 15
    num_matchups = len(matchups)
    num_variants = len(spec.variants)
    num_opponents = len(spec.evaluation.opponent_policies)
    num_seeds = len(spec.evaluation.evaluation_seeds)

    battles_per_seed = num_variants * num_opponents * num_matchups * 2 * pairs
    total_battles = battles_per_seed * num_seeds
    est_duration_seconds = round(total_battles * 5.44, 1)

    return {
        "status": "frozen",
        "test_teams": list(spec.evaluation.test_teams),
        "opponent_policies": list(spec.evaluation.opponent_policies),
        "evaluation_seeds": list(spec.evaluation.evaluation_seeds),
        "variants": spec.variants,
        "matchup_pairs": matchup_pairs,
        "pairs_per_matchup": pairs,
        "battles_per_seed": battles_per_seed,
        "total_evaluation_battles": total_battles,
        "estimated_duration_seconds": est_duration_seconds,
    }


def run_evaluation_battle(
    candidate_agent: BattleAgent,
    opponent_agent: BattleAgent,
    format_id: str,
    candidate_team: str,
    opponent_team: str,
    candidate_role: str = "p1",
    seed: tuple[int, int, int, int] | None = None,
    showdown_dir: Path | str | None = None,
    max_turns: int = 60,
) -> EvaluationBattleResult:
    """Execute a single evaluation battle between candidate and opponent."""
    start_time = time.perf_counter()
    cand_decisions = 0
    opp_decisions = 0
    cand_protect_uses = 0
    opp_protect_uses = 0
    protect_depleted = False

    candidate_agent.reset()
    opponent_agent.reset()

    if candidate_role == "p1":
        p1_agent = candidate_agent
        p2_agent = opponent_agent
        p1_team = candidate_team
        p2_team = opponent_team
    else:
        p1_agent = opponent_agent
        p2_agent = candidate_agent
        p1_team = opponent_team
        p2_team = candidate_team

    with ShowdownProcess(showdown_dir) as process:
        session = BattleSession(process)
        session.start(format_id, p1_agent.name, p1_team, p2_agent.name, p2_team, seed=seed)

        while not session.is_ended and session.turn < max_turns:
            p1_can_act = session.p1_request is not None and not session.p1_request.get(
                "wait", False
            )
            p2_can_act = session.p2_request is not None and not session.p2_request.get(
                "wait", False
            )

            if not p1_can_act and not p2_can_act:
                break

            if not protect_depleted:
                protect_depleted = _check_protect_depleted(
                    session.p1_request
                ) or _check_protect_depleted(session.p2_request)

            p1_choice = (
                p1_agent.choose_action(session.p1_request)
                if (p1_can_act and session.p1_request)
                else None
            )
            p2_choice = (
                p2_agent.choose_action(session.p2_request)
                if (p2_can_act and session.p2_request)
                else None
            )

            if candidate_role == "p1":
                if p1_can_act:
                    cand_decisions += 1
                    cand_protect_uses += _count_protect_choices(session.p1_request, p1_choice)
                if p2_can_act:
                    opp_decisions += 1
                    opp_protect_uses += _count_protect_choices(session.p2_request, p2_choice)
            else:
                if p1_can_act:
                    opp_decisions += 1
                    opp_protect_uses += _count_protect_choices(session.p1_request, p1_choice)
                if p2_can_act:
                    cand_decisions += 1
                    cand_protect_uses += _count_protect_choices(session.p2_request, p2_choice)

            turn_res = session.step(p1_choice, p2_choice)
            if turn_res.is_ended:
                break

        duration = time.perf_counter() - start_time
        candidate_won = session.winner == candidate_agent.name
        return EvaluationBattleResult(
            winner=session.winner,
            turns=session.turn,
            duration_seconds=duration,
            candidate_decisions=cand_decisions,
            opponent_decisions=opp_decisions,
            candidate_protect_uses=cand_protect_uses,
            opponent_protect_uses=opp_protect_uses,
            protect_depleted=protect_depleted,
            candidate_won=candidate_won,
        )


def run_evaluation_suite(
    spec: ExperimentSpec,
    manifest: TeamManifest,
    candidate: BattleAgent | str = "heuristic",
    opponent_policies: Sequence[str] | None = None,
    evaluation_seeds: Sequence[int] | None = None,
    variants: Sequence[str] | None = None,
    pairs_per_matchup: int | None = None,
    showdown_dir: Path | str | None = None,
) -> EvaluationSummary:
    """Execute evaluation matches across frozen test teams, opponents, and seeds."""
    verify_frozen_evaluation(spec, manifest)
    assert spec.evaluation is not None

    cand_agent = create_candidate_agent(candidate)
    target_opponents = tuple(opponent_policies or spec.evaluation.opponent_policies)
    target_seeds = tuple(evaluation_seeds or spec.evaluation.evaluation_seeds)
    target_variants = tuple(variants or tuple(spec.variants.keys()))
    pairs = pairs_per_matchup if pairs_per_matchup is not None else 1

    matchups = build_test_matchups(manifest, spec.evaluation.test_teams)

    matchup_summaries: list[MatchupEvaluationSummary] = []
    total_matches = 0
    candidate_wins = 0
    opponent_wins = 0
    ties = 0
    total_turns = 0
    total_duration = 0.0
    total_decisions = 0

    for var_idx, var_name in enumerate(target_variants):
        pp = spec.variants[var_name]
        format_id = FORMAT_BY_PP[pp]

        for _s_idx, eval_seed in enumerate(target_seeds):
            for opp_idx, opp_name in enumerate(target_opponents):
                opp_agent = create_opponent_agent(opp_name, seed=eval_seed)

                for m_idx, (t1_id, t1_packed, t2_id, t2_packed) in enumerate(matchups):
                    m_cand_wins = 0
                    m_opp_wins = 0
                    m_ties = 0
                    m_turns = 0
                    m_cand_protect = 0
                    m_opp_protect = 0
                    m_depleted_count = 0

                    for pair in range(pairs):
                        # Game 1: Candidate plays t1 as P1, Opponent plays t2 as P2
                        seed_g1 = make_eval_battle_seed(eval_seed, var_idx, opp_idx, m_idx, pair, 0)
                        res1 = run_evaluation_battle(
                            candidate_agent=cand_agent,
                            opponent_agent=opp_agent,
                            format_id=format_id,
                            candidate_team=t1_packed,
                            opponent_team=t2_packed,
                            candidate_role="p1",
                            seed=seed_g1,
                            showdown_dir=showdown_dir,
                        )

                        # Game 2: Opponent plays t1 as P1, Candidate plays t2 as P2
                        seed_g2 = make_eval_battle_seed(eval_seed, var_idx, opp_idx, m_idx, pair, 1)
                        res2 = run_evaluation_battle(
                            candidate_agent=cand_agent,
                            opponent_agent=opp_agent,
                            format_id=format_id,
                            candidate_team=t2_packed,
                            opponent_team=t1_packed,
                            candidate_role="p2",
                            seed=seed_g2,
                            showdown_dir=showdown_dir,
                        )

                        for r in (res1, res2):
                            total_matches += 1
                            total_turns += r.turns
                            total_duration += r.duration_seconds
                            total_decisions += r.candidate_decisions + r.opponent_decisions
                            m_turns += r.turns
                            m_cand_protect += r.candidate_protect_uses
                            m_opp_protect += r.opponent_protect_uses
                            if r.protect_depleted:
                                m_depleted_count += 1

                            if r.candidate_won:
                                candidate_wins += 1
                                m_cand_wins += 1
                            elif r.winner == opp_agent.name:
                                opponent_wins += 1
                                m_opp_wins += 1
                            else:
                                ties += 1
                                m_ties += 1

                    pair_matches = pairs * 2
                    matchup_summaries.append(
                        MatchupEvaluationSummary(
                            variant=var_name,
                            eval_seed=eval_seed,
                            opponent_policy=opp_name,
                            team_candidate=t1_id,
                            team_opponent=t2_id,
                            total_matches=pair_matches,
                            candidate_wins=m_cand_wins,
                            opponent_wins=m_opp_wins,
                            ties=m_ties,
                            win_rate=m_cand_wins / max(pair_matches, 1),
                            avg_turns=m_turns / max(pair_matches, 1),
                            candidate_protect_uses=m_cand_protect,
                            opponent_protect_uses=m_opp_protect,
                            protect_depleted_matches=m_depleted_count,
                        )
                    )

    overall_win_rate = candidate_wins / max(total_matches, 1)
    avg_turns = total_turns / max(total_matches, 1)
    dps = total_decisions / max(total_duration, 0.001)

    return EvaluationSummary(
        candidate_name=cand_agent.name,
        variants=target_variants,
        eval_seeds=target_seeds,
        opponent_policies=target_opponents,
        test_teams=spec.evaluation.test_teams,
        total_matches=total_matches,
        candidate_wins=candidate_wins,
        opponent_wins=opponent_wins,
        ties=ties,
        overall_win_rate=overall_win_rate,
        avg_turns=avg_turns,
        total_duration_seconds=round(total_duration, 3),
        decisions_per_second=round(dps, 2),
        matchup_summaries=tuple(matchup_summaries),
    )
