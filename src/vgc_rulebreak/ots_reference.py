"""Sourced, evaluation-only Champions OTS reference matchups for Study F."""

import hashlib
import json
import re
import subprocess
from datetime import date
from itertools import combinations
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from vgc_rulebreak.champions import load_champions_regulation
from vgc_rulebreak.full_transfer import REGULATION_PATH, SIMULATOR_REVISION
from vgc_rulebreak.manifest import _object, _text
from vgc_rulebreak.simulator.process import ShowdownProcess

MANIFEST_PATH = Path("experiments/teams/full-transfer-ots.json")
LEGALITY_FORMAT = "gen9championsvgc2026regmb"
OTS_FORMAT = LEGALITY_FORMAT + "@@@!Open Team Sheets,Force Open Team Sheets"
EVALUATION_SEEDS = (101, 202, 303)
SOURCE_FIELDS = {
    "family",
    "author",
    "title",
    "published",
    "retrieved",
    "report_url",
    "paste_url",
    "paste_context_url",
    "paste_file",
    "paste_sha256",
    "terms",
}


def load_reference_sources(path: Path) -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    """Verify attributed local source bytes before passing any team to the simulator."""
    doc = _object(
        json.loads(path.read_text(encoding="utf-8")),
        "OTS reference manifest",
        {"schema_version", "regulation_id", "legality_format", "regulation_source", "teams"},
    )
    if type(doc["schema_version"]) is not int or doc["schema_version"] != 1:
        raise ValueError("OTS reference schema_version must be 1")
    regulation = load_champions_regulation(REGULATION_PATH)
    if doc["regulation_id"] != regulation.regulation_id:
        raise ValueError("OTS references must identify the pinned Champions regulation")
    if doc["legality_format"] != LEGALITY_FORMAT:
        raise ValueError("OTS legality requires the explicit Regulation M-B format")
    if doc["regulation_source"] != "https://champions-news.pokemon-home.com/en/page/776.html":
        raise ValueError("OTS references must cite the Regulation M-B announcement")
    raw_teams = doc["teams"]
    if not isinstance(raw_teams, dict) or len(raw_teams) < 2:
        raise ValueError("OTS reference pool needs at least two teams")
    sources: dict[str, dict[str, str]] = {}
    pastes: dict[str, str] = {}
    families: set[str] = set()
    hashes: set[str] = set()
    for key, value in raw_teams.items():
        team_id = _text(key, "team ID")
        if not re.fullmatch(r"ots-[a-z0-9-]+", team_id):
            raise ValueError("reference team IDs must start with ots-")
        source = {
            field: _text(item, field)
            for field, item in _object(value, team_id, SOURCE_FIELDS).items()
        }
        for field in ("report_url", "paste_url", "paste_context_url"):
            url = urlparse(source[field])
            if url.scheme != "https" or not url.netloc:
                raise ValueError(f"{field} must be an absolute HTTPS URL")
        if not re.fullmatch(r"https://pokepast\.es/[a-f0-9]{16}", source["paste_url"]):
            raise ValueError("paste_url must identify a public Pokepaste")
        if not re.fullmatch(r"\d{4}-\d{2}(?:-\d{2})?", source["published"]):
            raise ValueError("published must be an ISO date or month")
        published = date.fromisoformat(
            source["published"] + ("-01" if len(source["published"]) == 7 else "")
        )
        retrieved = date.fromisoformat(source["retrieved"])
        if published > retrieved:
            raise ValueError("publication cannot follow retrieval")
        paste_file = (path.parent / source["paste_file"]).resolve()
        if not paste_file.is_relative_to(path.parent.resolve()) or paste_file.suffix != ".txt":
            raise ValueError("paste_file must be a local .txt file under the manifest directory")
        raw = paste_file.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != source["paste_sha256"]:
            raise ValueError(f"{team_id}: source paste SHA-256 mismatch")
        if source["family"] in families or digest in hashes:
            raise ValueError("reference families and source pastes must be distinct")
        families.add(source["family"])
        hashes.add(digest)
        sources[team_id] = source
        pastes[team_id] = raw.decode("utf-8")
    return sources, pastes


def build_ots_references(
    output_dir: Path,
    showdown_dir: Path | str | None = None,
    manifest_path: Path = MANIFEST_PATH,
) -> dict[str, Any]:
    """Validate real teams, build mirrored pairings, and verify OTS at team preview."""
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("output directory must be empty; evidence is never overwritten")
    sources, pastes = load_reference_sources(manifest_path)
    simulator = ShowdownProcess._resolve_showdown_dir(showdown_dir).resolve()
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=simulator, check=True, capture_output=True, text=True
    ).stdout.strip()
    clean = subprocess.run(["git", "diff", "--quiet", "HEAD"], cwd=simulator, check=False)
    if revision != SIMULATOR_REVISION or clean.returncode:
        raise ValueError("Simulator must be a clean checkout of the pinned revision")
    subprocess.run(["node", "build"], cwd=simulator, check=True, capture_output=True)
    matchups = [
        {"p1": left, "p2": right, "seed": [seed, 2, 3, 4]}
        for a, b in combinations(sorted(pastes), 2)
        for seed in EVALUATION_SEEDS
        for left, right in ((a, b), (b, a))
    ]
    probe = Path(__file__).with_name("simulator") / "ots_reference.cjs"
    result = subprocess.run(
        ["node", str(probe)],
        cwd=simulator,
        check=True,
        capture_output=True,
        text=True,
        input=json.dumps(
            {
                "pastes": pastes,
                "matchups": matchups,
                "legality_format": LEGALITY_FORMAT,
                "ots_format": OTS_FORMAT,
            }
        ),
        timeout=120,
    )
    evidence = json.loads(result.stdout)
    if set(evidence["teams"]) != set(sources) or len(evidence["setups"]) != len(matchups):
        raise ValueError("simulator returned incomplete OTS reference evidence")
    report = {
        "schema_version": 1,
        "command": "build-ots-references",
        "simulator_revision": revision,
        "regulation_id": load_champions_regulation(REGULATION_PATH).regulation_id,
        "legality_format": LEGALITY_FORMAT,
        "battle_format": OTS_FORMAT,
        "regulation_source": "https://champions-news.pokemon-home.com/en/page/776.html",
        "split": "reference-only; excluded from training and checkpoint selection",
        "sources": sources,
        "input_sha256": {
            str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (manifest_path, REGULATION_PATH, Path(__file__), probe)
        },
        "evaluation_seeds": EVALUATION_SEEDS,
        "matchups": matchups,
        **evidence,
        "limits": [
            "Legality is certified against pinned Showdown Regulation M-B, not game software.",
            "M-B begins June 17; the existing June custom-game declaration is not a legal format.",
            "Reports include later M-B teams; this is not a June usage or tournament sample.",
            "Preview uses default first-four selection; no policy strength or outcome estimate.",
            "Champions OTS reveals nature but excludes stat points and IVs.",
            "No SV legality, matched source-domain conversion, or OTS-aware agent claim.",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "ots_references.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report
