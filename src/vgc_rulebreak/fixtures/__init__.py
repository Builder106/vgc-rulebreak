"""Fixtures package for vgc-rulebreak."""

from vgc_rulebreak.fixtures.mechanics import (
    MechanicsReport,
    ProtectPPVerification,
    RageFistVerification,
    SpeedStatsVerification,
    verify_all_mechanics,
    verify_protect_pp,
    verify_rage_fist,
    verify_speed_stats,
)
from vgc_rulebreak.fixtures.teams import FIXTURE_TEAM_P1, FIXTURE_TEAM_P2

__all__ = [
    "FIXTURE_TEAM_P1",
    "FIXTURE_TEAM_P2",
    "MechanicsReport",
    "ProtectPPVerification",
    "RageFistVerification",
    "SpeedStatsVerification",
    "verify_all_mechanics",
    "verify_protect_pp",
    "verify_rage_fist",
    "verify_speed_stats",
]
