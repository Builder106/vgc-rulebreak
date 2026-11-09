"""Source integrity, regulated legality and the actual public OTS boundary."""

import hashlib
import json
import shutil
import subprocess
from collections import Counter
from pathlib import Path

import pytest

from vgc_rulebreak.cli import main
from vgc_rulebreak.ots_reference import MANIFEST_PATH, build_ots_references, load_reference_sources
from vgc_rulebreak.simulator.process import ShowdownProcess


def local_manifest(tmp_path: Path) -> Path:
    shutil.copytree(MANIFEST_PATH.parent / "ots", tmp_path / "ots")
    path = tmp_path / "manifest.json"
    path.write_bytes(MANIFEST_PATH.read_bytes())
    return path


def test_source_integrity_and_attribution() -> None:
    sources, pastes = load_reference_sources(MANIFEST_PATH)
    assert set(sources) == set(pastes) == {"ots-sand", "ots-snow", "ots-rain"}
    assert {s["author"] for s in sources.values()} == {"Onion", "Lycopoky", "freezai"}
    assert all(s["retrieved"] == "2026-11-09" for s in sources.values())
    # Retain source spelling, spreads and line endings; do not silently fix a paste.
    assert "Swampert-Mega" in pastes["ots-rain"]
    assert "32 HP / 8 Def / 9 SpA / 2 SpD / 15 Spe" in pastes["ots-snow"]
    assert "\r\n" in pastes["ots-sand"]


@pytest.mark.parametrize(
    "defect", ["hash", "author", "date", "future", "url", "format", "path", "family", "single"]
)
def test_reject_incomplete_or_changed_provenance(tmp_path: Path, defect: str) -> None:
    path = local_manifest(tmp_path)
    doc = json.loads(path.read_text())
    source = doc["teams"]["ots-sand"]
    if defect == "hash":
        (tmp_path / "ots/sand.txt").write_text("changed")
    elif defect == "author":
        source["author"] = ""
    elif defect == "date":
        source["published"] = "2026-13"
    elif defect == "future":
        source["published"] = "2027-01"
    elif defect == "url":
        source["report_url"] = "missing"
    elif defect == "format":
        doc["legality_format"] = "gen9championsdoublescustomgame"
    elif defect == "path":
        source["paste_file"] = "../outside.txt"
    elif defect == "family":
        source["family"] = "snow"
    else:
        doc["teams"] = {"ots-sand": source}
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError):
        load_reference_sources(path)


def test_output_is_not_overwritten(tmp_path: Path) -> None:
    path = tmp_path / "ots_references.json"
    path.write_text("original")
    with pytest.raises(ValueError, match="never overwritten"):
        build_ots_references(tmp_path)
    assert path.read_text() == "original"


@pytest.mark.parametrize("revision,dirty", [("wrong", 0), ("pinned", 1)])
def test_reject_unpinned_or_dirty_simulator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, revision: str, dirty: int
) -> None:
    from vgc_rulebreak.full_transfer import SIMULATOR_REVISION

    responses = iter(
        [
            subprocess.CompletedProcess(
                [], 0, SIMULATOR_REVISION if revision == "pinned" else revision
            ),
            subprocess.CompletedProcess([], dirty),
        ]
    )
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: next(responses))
    with pytest.raises(ValueError, match="clean checkout"):
        build_ots_references(tmp_path / "output", showdown_dir=tmp_path)
    assert not (tmp_path / "output").exists()


def test_cli_provenance_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert (
        main(
            [
                "build-ots-references",
                "--manifest",
                str(tmp_path / "missing.json"),
                "--output-dir",
                str(tmp_path / "output"),
            ]
        )
        == 2
    )
    assert "OTS reference error" in capsys.readouterr().err


def showdown_available() -> bool:
    try:
        ShowdownProcess._resolve_showdown_dir(None)
        return True
    except FileNotFoundError:
        return False


@pytest.mark.skipif(not showdown_available(), reason="Showdown not found")
def test_live_legal_references_mirrored_matchups_and_public_sheets(tmp_path: Path) -> None:
    report = build_ots_references(tmp_path)
    assert len(report["teams"]) == 3
    assert len(report["setups"]) == len(report["matchups"]) == 18
    cells = Counter((s["p1"], s["p2"]) for s in report["setups"])
    assert len(cells) == 6 and set(cells.values()) == {3}
    for setup in report["setups"]:
        reverse = {**setup, "p1": setup["p2"], "p2": setup["p1"]}
        assert any(
            all(other[k] == reverse[k] for k in ("p1", "p2", "seed")) for other in report["setups"]
        )
        assert setup["selected_members"] == 4 and setup["active_members"] == 2
        assert len(setup["public_sheets"]) == 2
        for sheet in setup["public_sheets"]:
            members = sheet.split("|", 3)[3].split("]")
            assert len(members) == 6
            for member in members:
                fields = member.split("|")
                assert fields[5] and not fields[6] and not fields[8]
    for team in report["teams"].values():
        assert len(team["private_team"]) == 6
        assert all(sum(p["evs"].values()) == 66 for p in team["private_team"])
    normalizations = report["teams"]["ots-rain"]["normalization"]
    assert {p["battle_species"] for p in normalizations} == {"Swampert", "Venusaur"}
    assert json.loads((tmp_path / "ots_references.json").read_text())["setups"] == report["setups"]


@pytest.mark.skipif(not showdown_available(), reason="Showdown not found")
@pytest.mark.parametrize(
    "before,after,error",
    [
        ("Leftovers", "Heavy-Duty Boots", "does not exist"),
        ("Overcoat", "Drizzle", "can't have"),
        ("Clanging Scales", "Astral Barrage", "can't learn"),
        ("5 HP / 32 SpA / 29 Spe", "32 HP / 32 SpA / 29 Spe", "66"),
        ("5 HP / 32 SpA / 29 Spe", "5 HP / 33 SpA / 28 Spe", "32 Stat Points"),
        ("Modest Nature", "IVs: 0 Spe\nModest Nature", "IVs are not maxed"),
        ("Life Orb", "Leftovers", "Item Clause"),
        ("Excadrill (F)", "Kommo-o (F)", "Species Clause"),
        ("- Protect", "", "incomplete sets"),
    ],
)
def test_live_regulation_rejects_illegal_source_sets(
    tmp_path: Path, before: str, after: str, error: str
) -> None:
    manifest = local_manifest(tmp_path)
    paste = tmp_path / "ots/sand.txt"
    paste.write_text(paste.read_text().replace(before, after, 1))
    doc = json.loads(manifest.read_text())
    doc["teams"]["ots-sand"]["paste_sha256"] = hashlib.sha256(paste.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(doc))
    with pytest.raises(subprocess.CalledProcessError) as raised:
        build_ots_references(tmp_path / "output", manifest_path=manifest)
    assert error in raised.value.stderr
    assert not (tmp_path / "output").exists()
