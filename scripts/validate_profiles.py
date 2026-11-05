#!/usr/bin/env python3
"""Validate filament profile files.

Usage:
  python scripts/validate_profiles.py                # check every profile in the repo
  python scripts/validate_profiles.py FILE [FILE...] # check only these (used by CI on PRs)
  python scripts/validate_profiles.py --community-only FILE...  # also reject changes in official/
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROFILE_EXT = {".json", ".ini", ".curaprofile", ".fff"}
MAX_SIZE = 512 * 1024  # 512 KB is far above any real preset

PART = r"[A-Za-z0-9.]+(?:-[A-Za-z0-9.]+)*"
OFFICIAL_RE = re.compile(rf"^3DTrcek_{PART}_{PART}_\d+(?:\.\d+)?(?:-[A-Za-z]+)*\.(json|ini|curaprofile|fff)$")
COMMUNITY_RE = re.compile(rf"^3DTrcek_{PART}_{PART}_\d+(?:\.\d+)?(?:-[A-Za-z]+)*_by-{PART}\.(json|ini|curaprofile|fff)$")

FILAMENT_KEYS = {
    "nozzle_temperature", "filament_type", "inherits", "filament_settings_id",
    "filament_flow_ratio", "filament_max_volumetric_speed", "hot_plate_temp",
}


def check(path: Path, community_only: bool) -> list[str]:
    errors = []
    rel = path.relative_to(ROOT).as_posix()
    top = rel.split("/")[0]

    if top not in ("official", "community"):
        return []  # not a profile location
    if path.suffix not in PROFILE_EXT:
        if path.name != ".gitkeep" and path.name.lower() != "readme.md":
            errors.append(f"{rel}: unsupported file type (use .json, .ini, .curaprofile or .fff)")
        return errors
    if community_only and top == "official":
        errors.append(f"{rel}: the official/ folder is maintained by 3DTrcek — put your profile in community/")
    if rel.count("/") < 2:
        errors.append(f"{rel}: put the file in a brand/model folder, e.g. community/prusa/MK4S/")

    pattern = OFFICIAL_RE if top == "official" else COMMUNITY_RE
    if not pattern.match(path.name):
        expected = ("3DTrcek_<Material>_<Printer>_<Nozzle>.<ext>" if top == "official"
                    else "3DTrcek_<Material>_<Printer>_<Nozzle>_by-<Name>.<ext>")
        errors.append(f"{rel}: file name should look like {expected} (no spaces or brackets)")

    if path.stat().st_size > MAX_SIZE:
        errors.append(f"{rel}: file is suspiciously large ({path.stat().st_size} bytes)")
        return errors

    if path.suffix == ".json":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            errors.append(f"{rel}: not valid JSON ({e})")
            return errors
        if not isinstance(data, dict) or not FILAMENT_KEYS & data.keys():
            errors.append(f"{rel}: doesn't look like a filament preset (no filament settings found)")
    return errors


def main(argv: list[str]) -> int:
    community_only = "--community-only" in argv
    args = [a for a in argv if not a.startswith("--")]
    if args:
        files = [ROOT / a for a in args if (ROOT / a).is_file()]
    else:
        files = [p for p in ROOT.joinpath("official").rglob("*") if p.is_file()]
        files += [p for p in ROOT.joinpath("community").rglob("*") if p.is_file()]

    errors = [e for f in files for e in check(f.resolve(), community_only)]
    for e in errors:
        print(f"::error::{e}")
    print(f"Checked {len(files)} file(s), {len(errors)} problem(s).")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
