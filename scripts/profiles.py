#!/usr/bin/env python3
"""3DTrcek filament profile library tools.

  python scripts/profiles.py validate                 check every profile
  python scripts/profiles.py validate FILE [FILE...]  check only these (CI on pull requests)
  python scripts/profiles.py validate --external ...  also block files credited to 3DTrcek (outside contributors)
  python scripts/profiles.py catalog                  regenerate CATALOG.md and catalog.json

Layout:   profiles/<brand>/<model>/<file>
File:     3DTrcek_<Material>_<Printer>_<Nozzle>_<Slicer>_by-<Author>.<ext>
Example:  profiles/prusa/MK4S/3DTrcek_PETG-Mat_MK4S_0.4_PrusaSlicer_by-janez.ini

Profiles credited "by-3DTrcek" are official (made and tested by the 3DTrcek team).
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
PROFILES = ROOT / "profiles"
REPO = "3DTrcek/3DTrcek-filament-profiles"
BRANCH = "main"
MAX_SIZE = 2 * 1024 * 1024

# Slicer token used in file names -> (display name, allowed extensions)
SLICERS: dict[str, tuple[str, set[str]]] = {
    "BambuStudio":        ("Bambu Studio",         {".json"}),
    "OrcaSlicer":         ("OrcaSlicer",           {".json"}),
    "CrealityPrint":      ("Creality Print",       {".json"}),
    "QIDIStudio":         ("QIDI Studio",          {".json"}),
    "ElegooSlicer":       ("ElegooSlicer",         {".json"}),
    "AnycubicSlicerNext": ("Anycubic Slicer Next", {".json"}),
    "PrusaSlicer":        ("PrusaSlicer",          {".ini"}),
    "SuperSlicer":        ("SuperSlicer",          {".ini"}),
    "Cura":               ("UltiMaker Cura",       {".curaprofile"}),
    "Simplify3D":         ("Simplify3D",           {".fff"}),
    "FlashPrint":         ("FlashPrint",           {".zip", ".cfg"}),
    "ideaMaker":          ("ideaMaker",            {".zip", ".data", ".bin"}),
    "Other":              ("Other",                {".zip", ".json", ".ini", ".cfg"}),
}
ALL_EXT = set().union(*(e for _, e in SLICERS.values()))
IGNORED = {".gitkeep", "README.md"}

TOKEN = r"[A-Za-z0-9]+(?:[-.][A-Za-z0-9]+)*"
NAME_RE = re.compile(
    rf"^3DTrcek_(?P<material>{TOKEN})_(?P<printer>{TOKEN})_(?P<nozzle>\d+(?:\.\d+)?(?:-[A-Za-z]+)*)"
    rf"_(?P<slicer>[A-Za-z0-9]+)_by-(?P<author>{TOKEN})(?P<ext>\.[a-z0-9]+)$"
)
FILAMENT_KEYS = {
    "nozzle_temperature", "filament_type", "inherits", "filament_settings_id",
    "filament_flow_ratio", "filament_max_volumetric_speed", "hot_plate_temp",
}


@dataclass
class Profile:
    path: str
    brand: str
    model: str
    material: str
    printer: str
    nozzle: str
    slicer: str
    slicer_name: str
    author: str
    official: bool

    @property
    def url(self) -> str:
        return f"https://github.com/{REPO}/raw/{BRANCH}/{quote(self.path)}"


def parse(path: Path) -> tuple[Profile | None, list[str], list[str]]:
    """Return (profile, errors, warnings) for one file."""
    errors: list[str] = []
    warnings: list[str] = []
    rel = path.relative_to(ROOT).as_posix()
    parts = rel.split("/")

    if parts[0] != "profiles" or path.name in IGNORED:
        return None, [], []
    if len(parts) != 4:
        return None, [f"{rel}: put the file in profiles/<brand>/<model>/ (e.g. profiles/prusa/MK4S/)"], []

    _, brand, model, name = parts
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", brand):
        errors.append(f"{rel}: brand folder '{brand}' should be lowercase with dashes, e.g. 'bambu-lab', 'prusa'")
    if not re.fullmatch(TOKEN, model):
        errors.append(f"{rel}: model folder '{model}' should have no spaces, e.g. 'MK4S', 'Ender-3-V3', 'X1-P1'")

    m = NAME_RE.match(name)
    if not m:
        errors.append(f"{rel}: file name should be "
                      "3DTrcek_<Material>_<Printer>_<Nozzle>_<Slicer>_by-<Name>.<ext> "
                      "(no spaces or brackets), e.g. 3DTrcek_PETG-Mat_MK4S_0.4_PrusaSlicer_by-janez.ini")
        return None, errors, warnings

    g = m.groupdict()
    if g["slicer"] not in SLICERS:
        errors.append(f"{rel}: unknown slicer '{g['slicer']}'. Use one of: {', '.join(SLICERS)}")
        return None, errors, warnings
    slicer_name, exts = SLICERS[g["slicer"]]
    if g["ext"] not in exts:
        errors.append(f"{rel}: {slicer_name} profiles should be {' or '.join(sorted(exts))}, not {g['ext']}")
    if g["printer"].lower() != model.lower():
        warnings.append(f"{rel}: printer in file name ('{g['printer']}') differs from folder ('{model}')")

    size = path.stat().st_size
    if size > MAX_SIZE:
        errors.append(f"{rel}: file is too large ({size} bytes)")
    elif g["ext"] == ".json":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or not FILAMENT_KEYS & data.keys():
                errors.append(f"{rel}: doesn't look like a filament preset (no filament settings found)")
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            errors.append(f"{rel}: not valid JSON ({e})")
    elif g["ext"] == ".ini":
        head = path.read_text(encoding="utf-8", errors="replace")[:400].lower()
        made_by = "superslicer" if "superslicer" in head else "prusaslicer" if "prusaslicer" in head else None
        if made_by and made_by != g["slicer"].lower():
            warnings.append(f"{rel}: file header says it was made with {made_by}, name says {g['slicer']}")

    profile = Profile(
        path=rel, brand=brand, model=model, material=g["material"], printer=g["printer"],
        nozzle=g["nozzle"], slicer=g["slicer"], slicer_name=slicer_name, author=g["author"],
        official=g["author"].lower() == "3dtrcek",
    )
    return profile, errors, warnings


def all_files() -> list[Path]:
    return sorted(p for p in PROFILES.rglob("*") if p.is_file()) if PROFILES.exists() else []


# --------------------------------------------------------------------------- validate
def cmd_validate(args: list[str]) -> int:
    external = "--external" in args
    names = [a for a in args if not a.startswith("--")]
    files = [ROOT / n for n in names if (ROOT / n).is_file()] if names else all_files()

    n_err = 0
    for f in files:
        f = f.resolve()
        rel = f.relative_to(ROOT).as_posix()
        if not rel.startswith("profiles/") or f.name in IGNORED:
            continue
        if f.suffix not in ALL_EXT:
            print(f"::error::{rel}: unsupported file type '{f.suffix}'")
            n_err += 1
            continue
        profile, errors, warnings = parse(f)
        if external and profile and profile.official:
            errors.append(f"{rel}: 'by-3DTrcek' is reserved for official profiles – use your own name")
        for e in errors:
            print(f"::error::{e}")
        for w in warnings:
            print(f"::warning::{w}")
        n_err += len(errors)
    print(f"Checked {len(files)} file(s), {n_err} problem(s).")
    return 1 if n_err else 0


# --------------------------------------------------------------------------- catalog
def cmd_catalog(_args: list[str]) -> int:
    profiles: list[Profile] = []
    for f in all_files():
        p, errors, _ = parse(f)
        if p and not errors:
            profiles.append(p)

    profiles.sort(key=lambda p: (p.brand, p.model.lower(), p.material.lower(), not p.official, p.slicer, p.nozzle))

    (ROOT / "catalog.json").write_text(
        json.dumps([{**asdict(p), "download": p.url} for p in profiles], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")

    brands = sorted({p.brand for p in profiles})
    lines = [
        "# Profile catalog",
        "",
        "<!-- Generated automatically by scripts/profiles.py – do not edit by hand. -->",
        "",
        f"**{len(profiles)} profiles** for **{len({(p.brand, p.model) for p in profiles})} printers** "
        f"in **{len({p.slicer for p in profiles})} slicers**. "
        "Press <kbd>Ctrl</kbd>+<kbd>F</kbd> and type your printer or material.",
        "",
        "⭐ = official profile, tuned and tested by 3DTrcek.",
        "",
    ]
    if not profiles:
        lines += ["_No profiles yet – [be the first to share one](../../issues/new/choose)!_", ""]
    else:
        lines += ["**Jump to:** " + " · ".join(f"[{b.replace('-', ' ').title()}](#{b})" for b in brands), ""]
    for brand in brands:
        lines += [f'<a id="{brand}"></a>', f"## {brand.replace('-', ' ').title()}", ""]
        for model in sorted({p.model for p in profiles if p.brand == brand}, key=str.lower):
            lines += [f"### {model.replace('-', ' ')}", "",
                      "| Material | Nozzle | Slicer | By | Download |",
                      "|---|---|---|---|---|"]
            for p in (p for p in profiles if p.brand == brand and p.model == model):
                by = "⭐ 3DTrcek" if p.official else p.author
                lines.append(f"| {p.material.replace('-', ' ')} | {p.nozzle} | {p.slicer_name} | {by} | "
                             f"[⬇ {Path(p.path).suffix}]({p.url}) |")
            lines.append("")
    lines += ["---", "",
              "Missing your printer? [Share your profile](../../issues/new/choose) – it takes two minutes.", ""]
    (ROOT / "CATALOG.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Catalog: {len(profiles)} profiles")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("validate", "catalog"):
        print(__doc__)
        sys.exit(2)
    sys.exit({"validate": cmd_validate, "catalog": cmd_catalog}[sys.argv[1]](sys.argv[2:]))
