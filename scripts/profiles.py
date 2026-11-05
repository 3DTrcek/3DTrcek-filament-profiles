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
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))
import safety  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PROFILES = ROOT / "profiles"
REPO = "3DTrcek/3DTrcek-filament-profiles"
BRANCH = "main"
MAX_SIZE = 2 * 1024 * 1024

# Slicer token used in file names -> (display name, allowed extensions)
SLICERS: dict[str, tuple[str, set[str]]] = {
    "BambuStudio":        ("Bambu Studio",         {".json", ".bbsflmt"}),
    "OrcaSlicer":         ("OrcaSlicer",           {".json", ".orca_filament"}),
    "CrealityPrint":      ("Creality Print",       {".json"}),
    "QIDIStudio":         ("QIDI Studio",          {".json"}),
    "ElegooSlicer":       ("ElegooSlicer",         {".json"}),
    "AnycubicSlicerNext": ("Anycubic Slicer Next", {".json"}),
    "PrusaSlicer":        ("PrusaSlicer",          {".ini"}),
    "SuperSlicer":        ("SuperSlicer",          {".ini"}),
    "Cura":               ("UltiMaker Cura",       {".curaprofile"}),
    "Simplify3D":         ("Simplify3D",           {".fff"}),
}
# FlashPrint, ideaMaker and other slicers are reviewed by hand until we know their exact export format.
ALL_EXT = set().union(*(e for _, e in SLICERS.values()))
BUNDLE_EXT = {".bbsflmt", ".orca_filament"}
# Optional slicer subfolders: profiles/<brand>/<model>/<slicer-folder>/<file>
SLICER_FOLDERS = {
    "bambu-studio": "BambuStudio", "bambustudio": "BambuStudio",
    "orcaslicer": "OrcaSlicer", "orca-slicer": "OrcaSlicer", "orca": "OrcaSlicer",
    "creality-print": "CrealityPrint", "qidi-studio": "QIDIStudio", "elegooslicer": "ElegooSlicer",
    "anycubic-slicer-next": "AnycubicSlicerNext", "prusaslicer": "PrusaSlicer", "superslicer": "SuperSlicer",
    "cura": "Cura", "simplify3d": "Simplify3D",
}
IGNORED = {".gitkeep", "README.md"}

TOKEN = r"[A-Za-z0-9]+(?:[-.][A-Za-z0-9]+)*"
NAME_RE = re.compile(
    rf"^3DTrcek_(?P<material>{TOKEN})_(?P<printer>{TOKEN})_(?P<nozzle>\d+(?:\.\d+)?(?:-[A-Za-z]+)*)"
    rf"_(?P<slicer>[A-Za-z0-9]+)_by-(?P<author>{TOKEN})(?P<ext>\.[a-z0-9_]+)$"
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
    covers: str = ""

    @property
    def material_display(self) -> str:
        return self.material if " " in self.material else self.material.replace("-", " ")

    @property
    def url(self) -> str:
        return f"https://github.com/{REPO}/raw/{BRANCH}/{quote(self.path)}"


def _bundle_info(path: Path) -> tuple[list[str], list[str]]:
    """For zip-based bundles: (nozzle sizes, printers) read from the preset names inside."""
    nozzles, printers = set(), set()
    try:
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                m = re.search(r"@(?:Bambu Lab )?(.+?) (\d+(?:\.\d+)?) nozzle", Path(name).stem)
                if m:
                    printers.add(m.group(1).strip())
                    nozzles.add(m.group(2))
    except zipfile.BadZipFile:
        pass
    return sorted(nozzles), sorted(printers)


def _loose_material(stem: str) -> str:
    stem = re.sub(r"(?i)^3d\s*tr[cč]ek[\s_-]*", "", stem)
    stem = re.sub(r"(?i)\s*@.*$", "", stem)              # "PLA Matte @Bambu Lab P1S" -> "PLA Matte"
    stem = re.sub(r"(?i)\s+filament$", "", stem)
    stem = re.sub(r"\s*-\s+", "-", stem)                  # "Wood- Bamboo" -> "Wood-Bamboo"
    return re.sub(r"[\s_]+", " ", stem).strip(" -") or "Unknown"


def parse(path: Path, strict: bool = False) -> tuple[Profile | None, list[str], list[str]]:
    """Return (profile, errors, warnings) for one file.

    strict=True (outside contributors): only the full naming convention is accepted.
    Otherwise team uploads may also be dropped into a slicer subfolder with the name
    the slicer exported – material, nozzle and slicer are worked out automatically.
    """
    errors: list[str] = []
    warnings: list[str] = []
    rel = path.relative_to(ROOT).as_posix()
    parts = rel.split("/")

    if parts[0] != "profiles" or path.name in IGNORED:
        return None, [], []
    if len(parts) not in (4, 5):
        return None, [f"{rel}: put the file in profiles/<brand>/<model>/ (e.g. profiles/prusa/MK4S/)"], []

    brand, model = parts[1], parts[2]
    folder_slicer = None
    if len(parts) == 5:
        folder_slicer = SLICER_FOLDERS.get(parts[3].lower())
        if not folder_slicer:
            return None, [f"{rel}: unknown slicer folder '{parts[3]}'. Use one of: "
                          f"{', '.join(sorted(set(SLICER_FOLDERS)))}"], []
    name = parts[-1]
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", brand):
        errors.append(f"{rel}: brand folder '{brand}' should be lowercase with dashes, e.g. 'bambu-lab', 'prusa'")
    if not re.fullmatch(TOKEN, model):
        errors.append(f"{rel}: model folder '{model}' should have no spaces, e.g. 'MK4S', 'Ender-3-V3', 'X1-P1'")

    ext = path.suffix.lower()
    m = NAME_RE.match(name)
    if m:
        g = m.groupdict()
        if g["slicer"] not in SLICERS:
            errors.append(f"{rel}: unknown slicer '{g['slicer']}'. Use one of: {', '.join(SLICERS)}")
            return None, errors, warnings
        if folder_slicer and folder_slicer != g["slicer"]:
            errors.append(f"{rel}: file name says {g['slicer']} but it is in the {parts[3]}/ folder")
        if g["printer"].lower() != model.lower():
            warnings.append(f"{rel}: printer in file name ('{g['printer']}') differs from folder ('{model}')")
        slicer, material, nozzle, author = g["slicer"], g["material"], g["nozzle"], g["author"]
    elif folder_slicer and not strict:
        slicer, author = folder_slicer, "3DTrcek"
        material = _loose_material(Path(name).stem)
        nozzles, _ = _bundle_info(path)
        nozzle = ", ".join(nozzles) if nozzles else "–"
    else:
        errors.append(f"{rel}: file name should be "
                      "3DTrcek_<Material>_<Printer>_<Nozzle>_<Slicer>_by-<Name>.<ext> "
                      "(no spaces or brackets), e.g. 3DTrcek_PETG-Mat_MK4S_0.4_PrusaSlicer_by-janez.ini")
        return None, errors, warnings

    slicer_name, exts = SLICERS[slicer]
    if ext not in exts:
        errors.append(f"{rel}: {slicer_name} profiles should be {' or '.join(sorted(exts))}, not {ext}")

    size = path.stat().st_size
    if size > MAX_SIZE:
        errors.append(f"{rel}: file is too large ({size} bytes)")
        return None, errors, warnings

    s_err, s_warn, _ = safety.scan_file(path, rel)
    errors += s_err
    warnings += s_warn

    if ext == ".json":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or not FILAMENT_KEYS & data.keys():
                errors.append(f"{rel}: doesn't look like a filament preset (no filament settings found)")
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            errors.append(f"{rel}: not valid JSON ({e})")
    elif ext in BUNDLE_EXT:
        if not zipfile.is_zipfile(path):
            errors.append(f"{rel}: not a valid {slicer_name} preset bundle")
    elif ext == ".ini":
        head = path.read_text(encoding="utf-8", errors="replace")[:400].lower()
        made_by = "superslicer" if "superslicer" in head else "prusaslicer" if "prusaslicer" in head else None
        if made_by and made_by != slicer.lower():
            warnings.append(f"{rel}: file header says it was made with {made_by}, name says {slicer}")

    covers = ", ".join(_bundle_info(path)[1]) if ext in BUNDLE_EXT else ""
    profile = Profile(
        path=rel, brand=brand, model=model, material=material, printer=model,
        nozzle=nozzle, slicer=slicer, slicer_name=slicer_name, author=author,
        official=author.lower() == "3dtrcek", covers=covers,
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
        if f.suffix.lower() not in ALL_EXT:
            print(f"::error::{rel}: unsupported file type '{f.suffix}'")
            n_err += 1
            continue
        profile, errors, warnings = parse(f, strict=external)
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

    profiles.sort(key=lambda p: (p.brand, p.model.lower(), p.material_display.lower(), not p.official, p.slicer, p.nozzle))

    (ROOT / "catalog.json").write_text(
        json.dumps([{**asdict(p), "download": p.url} for p in profiles], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")

    brands = sorted({p.brand for p in profiles})
    n_printers = len({(p.brand, p.model) for p in profiles})
    n_slicers = len({p.slicer for p in profiles})
    lines = [
        "# Profile catalog",
        "",
        "<!-- Generated automatically by scripts/profiles.py – do not edit by hand. -->",
        "",
        f"**{len(profiles)} profiles** · **{n_printers} printer{'s' if n_printers != 1 else ''}** · "
        f"**{n_slicers} slicer{'s' if n_slicers != 1 else ''}**. "
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
                      "| Material | Nozzle | Slicer | Presets for | By | Download |",
                      "|---|---|---|---|---|---|"]
            for p in (p for p in profiles if p.brand == brand and p.model == model):
                by = "⭐ 3DTrcek" if p.official else p.author.replace("-", " ")
                lines.append(f"| {p.material_display} | {p.nozzle} | {p.slicer_name} | {p.covers or p.model.replace('-', ' ')} | {by} | "
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
