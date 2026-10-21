"""Battle agents and benchmarking tools for vgc-rulebreak."""

from vgc_rulebreak.agents.base import BattleAgent
from vgc_rulebreak.agents.benchmark import (
    AgentBenchmarkReport,
    MatchResult,
    benchmark_agent_pair,
    run_battle,
)
from vgc_rulebreak.agents.heuristic import HeuristicAgent
from vgc_rulebreak.agents.random import RandomAgent
from vgc_rulebreak.agents.variants import AdaptedAgent, NativeAgent, SourceAgent

__all__ = [
    "AdaptedAgent",
    "AgentBenchmarkReport",
    "BattleAgent",
    "HeuristicAgent",
    "MatchResult",
    "NativeAgent",
    "RandomAgent",
    "SourceAgent",
    "benchmark_agent_pair",
    "run_battle",
]
