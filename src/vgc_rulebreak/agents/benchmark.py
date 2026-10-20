"""Agent evaluation and performance benchmarking runner."""

import time
from dataclasses import dataclass
from pathlib import Path

from vgc_rulebreak.agents.base import BattleAgent
from vgc_rulebreak.fixtures.teams import (
    OTS_TEAM_SUN,
    OTS_TEAM_TAILWIND,
)
from vgc_rulebreak.simulator.battle import BattleSession
from vgc_rulebreak.simulator.process import ShowdownProcess


@dataclass(frozen=True)
class MatchResult:
    winner: str | None
    turns: int
    duration_seconds: float
    p1_decisions: int
    p2_decisions: int


@dataclass(frozen=True)
class AgentBenchmarkReport:
    total_matches: int
    p1_agent_name: str
    p2_agent_name: str
    p1_wins: int
    p2_wins: int
    ties: int
    p1_win_rate: float
    avg_turns: float
    total_duration_seconds: float
    decisions_per_second: float
    avg_turn_latency_ms: float


def run_battle(
    p1_agent: BattleAgent,
    p2_agent: BattleAgent,
    format_id: str = "gen9doublescustomgame",
    p1_team: str = OTS_TEAM_SUN,
    p2_team: str = OTS_TEAM_TAILWIND,
    seed: tuple[int, int, int, int] | None = None,
    showdown_dir: Path | str | None = None,
    max_turns: int = 60,
) -> MatchResult:
    """Execute a single battle to completion between two agents."""
    start_time = time.perf_counter()
    p1_decisions = 0
    p2_decisions = 0

    p1_agent.reset()
    p2_agent.reset()

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

            if p1_can_act:
                p1_decisions += 1
            if p2_can_act:
                p2_decisions += 1

            turn_res = session.step(p1_choice, p2_choice)
            if turn_res.is_ended:
                break

        duration = time.perf_counter() - start_time
        return MatchResult(
            winner=session.winner,
            turns=session.turn,
            duration_seconds=duration,
            p1_decisions=p1_decisions,
            p2_decisions=p2_decisions,
        )


def benchmark_agent_pair(
    p1_agent: BattleAgent,
    p2_agent: BattleAgent,
    matches: int = 10,
    format_id: str = "gen9doublescustomgame",
    p1_team: str = OTS_TEAM_SUN,
    p2_team: str = OTS_TEAM_TAILWIND,
    showdown_dir: Path | str | None = None,
) -> AgentBenchmarkReport:
    """Run multiple matches between two agents and compile performance metrics."""
    p1_wins = 0
    p2_wins = 0
    ties = 0
    total_turns = 0
    total_duration = 0.0
    total_decisions = 0

    for m in range(matches):
        team_p1 = p1_team if m % 2 == 0 else p2_team
        team_p2 = p2_team if m % 2 == 0 else p1_team
        res = run_battle(
            p1_agent=p1_agent,
            p2_agent=p2_agent,
            format_id=format_id,
            p1_team=team_p1,
            p2_team=team_p2,
            seed=(1000 + m, 2000 + m, 3000 + m, 4000 + m),
            showdown_dir=showdown_dir,
        )
        if res.winner == p1_agent.name:
            p1_wins += 1
        elif res.winner == p2_agent.name:
            p2_wins += 1
        else:
            ties += 1

        total_turns += res.turns
        total_duration += res.duration_seconds
        total_decisions += res.p1_decisions + res.p2_decisions

    avg_turns = total_turns / max(matches, 1)
    win_rate = p1_wins / max(matches, 1)
    dps = total_decisions / max(total_duration, 0.001)
    avg_latency = (total_duration / max(total_turns, 1)) * 1000.0

    return AgentBenchmarkReport(
        total_matches=matches,
        p1_agent_name=p1_agent.name,
        p2_agent_name=p2_agent.name,
        p1_wins=p1_wins,
        p2_wins=p2_wins,
        ties=ties,
        p1_win_rate=win_rate,
        avg_turns=avg_turns,
        total_duration_seconds=total_duration,
        decisions_per_second=dps,
        avg_turn_latency_ms=avg_latency,
    )
