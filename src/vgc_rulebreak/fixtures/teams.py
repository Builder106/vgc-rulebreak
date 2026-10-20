"""Standardized packed teams for mechanics fixtures and tests."""

# Packed format:
# name|species|item|ability|moves|nature|evs|gender|ivs|shiny|level|happiness,teraType

# Standard test team with Annihilape and support
FIXTURE_TEAM_P1 = (
    "Annihilape||leftovers|vitalspirit|ragefist,protect,drainpunch,finalgambit"
    "|Jolly|252,4,0,0,0,252|||50|,,Ghost"
    "]Flutter Mane||boosterenergy|protosynthesis|moonblast,shadowball,protect,dazzlinggleam"
    "|Timid|0,0,4,252,0,252|||50|,,Fairy"
)

# Standard test team with opponent moves (Bite to trigger hit counter, Protect for passive turns)
FIXTURE_TEAM_P2 = (
    "Eevee||eviolite|runaway|bite,protect,tackle,quickattack|Serious|0,0,0,0,0,0|||50|,,Normal"
    "]Ogerpon-Wellspring||wellspringmask|waterabsorb|ivycudgel,spikyshield,followme,hornleech"
    "|Jolly|252,4,0,0,0,252|||50|,,Water"
)
