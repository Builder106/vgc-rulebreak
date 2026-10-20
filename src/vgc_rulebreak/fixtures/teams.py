"""Standardized packed teams for mechanics fixtures and tests."""

# Packed format:
# name|species|item|ability|moves|nature|evs|gender|ivs|shiny|level|
# happiness,teraType,pokeball,hpType,gigantamax,dynamaxLevel

# Standard 2-mon test teams for mechanics checks
FIXTURE_TEAM_P1 = (
    "Flutter Mane||BoosterEnergy|Protosynthesis|Moonblast,ShadowBall,DazzlingGleam,Protect"
    "|Timid|4,,,252,,252||||50|,,,,,Fairy"
    "]Annihilape||Leftovers|VitalSpirit|RageFist,DrainPunch,FinalGambit,Protect"
    "|Jolly|252,,4,,,252||||50|,,,,,Ghost"
)

FIXTURE_TEAM_P2 = (
    "Eevee||Eviolite|RunAway|Bite,Protect,Tackle,QuickAttack|Serious|||||50|,,,,,Normal"
    "]Ogerpon-Wellspring||WellspringMask|WaterAbsorb|IvyCudgel,HornLeech,FollowMe,SpikyShield"
    "|Jolly|252,76,20,,4,156|||||,,,,,Water"
)

# Full 6-mon Open Team Sheet (OTS) archetypes for benchmarks
OTS_TEAM_TAILWIND = (
    "Tornadus||CovertCloak|Prankster|Tailwind,BleakwindStorm,Taunt,Protect"
    "|Timid|252,,116,4,76,60|||||,,,,,Ghost"
    "]Flutter Mane||BoosterEnergy|Protosynthesis|Moonblast,ShadowBall,DazzlingGleam,Protect"
    "|Timid|116,,188,116,4,84|||||,,,,,Fairy"
    "]Urshifu-Rapid-Strike||ChoiceScarf|UnseenFist|SurgingStrikes,CloseCombat,AquaJet,Uturn"
    "|Adamant|4,252,,,,252|||||,,,,,Water"
    "]Rillaboom||AssaultVest|GrassySurge|GrassyGlide,WoodHammer,HighHorsepower,Uturn"
    "|Adamant|252,196,20,,36,4|||||,,,,,Fire"
    "]Ogerpon-Wellspring||WellspringMask|WaterAbsorb|IvyCudgel,HornLeech,FollowMe,SpikyShield"
    "|Jolly|252,76,20,,4,156|||||,,,,,Water"
    "]Chien-Pao||FocusSash|SwordofRuin|IcicleCrash,SuckerPunch,SacredSword,Protect"
    "|Jolly|4,252,,,,252|||||,,,,,Ghost"
)

OTS_TEAM_SUN = (
    "Torkoal||Charcoal|Drought|Eruption,HeatWave,SolarBeam,Protect"
    "|Quiet|252,,,252,4,|||||,,,,,Fire"
    "]Chi-Yu||ChoiceSpecs|Beads of Ruin|HeatWave,DarkPulse,Overheat,Snarl"
    "|Modest|4,,,252,,252|||||,,,,,Ghost"
    "]Flutter Mane||FocusSash|Protosynthesis|Moonblast,ShadowBall,IcyWind,Protect"
    "|Timid|4,,,252,,252|||||,,,,,Fairy"
    "]Rillaboom||MiracleSeed|GrassySurge|GrassyGlide,WoodHammer,FakeOut,Protect"
    "|Adamant|252,252,4,,,|||||,,,,,Grass"
    "]Urshifu||BlackGlasses|UnseenFist|WickedBlow,CloseCombat,SuckerPunch,Detect"
    "|Adamant|4,252,,,,252|||||,,,,,Dark"
    "]Farigiraf||SitrusBerry|ArmorTail|HyperVoice,Psychic,TrickRoom,Protect"
    "|Quiet|252,,156,100,,|||||,,,,,Fairy"
)
