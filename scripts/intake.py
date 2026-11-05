#!/usr/bin/env python3
"""Turn an approved profile-submission issue into a pull request.

Runs in GitHub Actions when a maintainer adds the `approved` label to an issue
created from the "Submit a filament profile" form. It:

  1. reads the form answers from the issue body,
  2. downloads the attached profile file (unzipping it if needed),
  3. builds the correct folder and file name,
  4. validates the result with scripts/profiles.py,
  5. commits it on a new branch, opens a pull request and comments on the issue.

The issue body is untrusted input: it is only ever parsed in Python and never
passed through a shell.

Local test (no network / git):  python scripts/intake.py --dry-run event.json [local-file]
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import profiles as lib  # noqa: E402
import safety  # noqa: E402

ROOT = lib.ROOT
MAX_DOWNLOAD = 5 * 1024 * 1024

SLICER_TOKENS = {
    "Bambu Studio": "BambuStudio",
    "OrcaSlicer": "OrcaSlicer",
    "PrusaSlicer": "PrusaSlicer",
    "UltiMaker Cura": "Cura",
    "Creality Print": "CrealityPrint",
    "QIDI Studio": "QIDIStudio",
    "ElegooSlicer": "ElegooSlicer",
    "Anycubic Slicer Next": "AnycubicSlicerNext",
    "SuperSlicer": "SuperSlicer",
    "Simplify3D": "Simplify3D",
}
BRAND_SLUGS = {
    "Bambu Lab": "bambu-lab", "Prusa": "prusa", "Creality": "creality", "Elegoo": "elegoo",
    "Anycubic": "anycubic", "QIDI": "qidi", "Flashforge": "flashforge", "Sovol": "sovol",
    "Artillery": "artillery", "Anker / AnkerMake": "anker", "Snapmaker": "snapmaker",
    "UltiMaker": "ultimaker", "Raise3D": "raise3d",
}
DIY_BRANDS = {"voron": "voron", "ratrig": "ratrig", "rat-rig": "ratrig"}


class IntakeError(Exception):
    """A problem the maintainer or submitter needs to fix."""


# ----------------------------------------------------------------------------- parsing
def parse_form(body: str) -> dict[str, str]:
    """Issue-form bodies look like '### Label\\n\\nvalue\\n\\n### Next label…'."""
    fields: dict[str, str] = {}
    for block in re.split(r"^### ", body or "", flags=re.M)[1:]:
        label, _, value = block.partition("\n")
        value = value.strip()
        fields[label.strip()] = "" if value == "_No response_" else value
    return fields


def slug(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9.]+", "-", text.strip())
    return re.sub(r"-{2,}", "-", text).strip("-.")


def material_name(family: str, product: str) -> str:
    fam = family.split(" ")[0]  # "PA (Nylon)" -> "PA"
    prod = re.sub(r"(?i)^3d\s*tr[cč]ek\s*", "", product).strip()
    if not prod:
        prod = fam
    if fam.lower() != "other" and not prod.lower().startswith(fam.lower()):
        prod = f"{fam} {prod}"
    name = slug(prod)
    if not name:
        raise IntakeError("Could not work out the material name.")
    return name


def printer_location(brand_choice: str, model_text: str) -> tuple[str, str]:
    model_text = model_text.strip()
    if not model_text:
        raise IntakeError("Printer model is empty.")
    if brand_choice in BRAND_SLUGS:
        brand = BRAND_SLUGS[brand_choice]
        # drop the brand name if it was typed in front of the model ("Prusa MK4S" -> "MK4S")
        for word in [brand_choice, *brand_choice.split(" / "), brand.replace("-", " ")]:
            model_text = re.sub(rf"(?i)^{re.escape(word)}\s+", "", model_text)
    else:
        first, _, rest = model_text.partition(" ")
        key = first.lower()
        if brand_choice.startswith("Voron") and key not in DIY_BRANDS:
            brand = "diy"
        else:
            brand = DIY_BRANDS.get(key, slug(first).lower())
            model_text = rest or first
    model = slug(model_text)
    if not brand or not model:
        raise IntakeError("Could not work out the printer brand/model.")

    # reuse an existing folder if only the capitalisation differs
    brand_dir = lib.PROFILES / brand
    if brand_dir.is_dir():
        for existing in brand_dir.iterdir():
            if existing.is_dir() and existing.name.lower() == model.lower():
                model = existing.name
                break
    return brand, model


def nozzle_name(choice: str, checkboxes: str) -> str:
    m = re.match(r"(\d+(?:\.\d+)?)", choice)
    if not m:
        raise IntakeError("Nozzle diameter is 'Other' – please check the notes and add the profile by hand.")
    nozzle = m.group(1)
    if re.search(r"- \[[xX]\] High-flow", checkboxes):
        nozzle += "-HF"
    if re.search(r"- \[[xX]\] Hardened", checkboxes):
        nozzle += "-HS"
    return nozzle


def attachment_url(text: str) -> tuple[str, str]:
    links = re.findall(r"\[([^\]]+)\]\((https://github\.com/(?:user-attachments/files|[^)\s]+/files)/[^)\s]+)\)", text)
    if not links:
        raise IntakeError("No attached file found in the 'Profile file' field.")
    if len(links) > 1:
        raise IntakeError("More than one file is attached – please attach exactly one profile per submission.")
    return links[0][1], links[0][0]


# ----------------------------------------------------------------------------- file handling
def download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "3DTrcek-profile-bot"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read(MAX_DOWNLOAD + 1)
    if len(data) > MAX_DOWNLOAD:
        raise IntakeError("Attached file is larger than 5 MB.")
    dest.write_bytes(data)


def pick_profile_file(src: Path, original_name: str, allowed: set[str], workdir: Path) -> tuple[Path, str]:
    """Return (path to file to store, extension). Unzips if the slicer doesn't use zip."""
    ext = Path(original_name).suffix.lower()
    if ext == ".zip" and ".zip" not in allowed:
        with zipfile.ZipFile(src) as z:
            members = [m for m in z.namelist()
                       if not m.endswith("/") and Path(m).suffix.lower() in allowed and "__MACOSX" not in m]
            if len(members) != 1:
                raise IntakeError(f"The zip should contain exactly one {' / '.join(sorted(allowed))} file "
                                  f"(found {len(members)}).")
            out = workdir / "unzipped"
            out.write_bytes(z.read(members[0]))
            return out, Path(members[0]).suffix.lower()
    if ext not in allowed:
        raise IntakeError(f"This slicer's profiles should be {' or '.join(sorted(allowed))}, "
                          f"but the attached file is '{original_name}'.")
    return src, ext


# ----------------------------------------------------------------------------- main
def build(event: dict, local_file: Path | None, workdir: Path) -> dict:
    issue = event["issue"]
    f = parse_form(issue.get("body", ""))

    def need(label: str) -> str:
        v = f.get(label, "")
        if not v:
            raise IntakeError(f"The form field '{label}' is missing.")
        return v

    slicer_choice = need("Slicer")
    slicer = SLICER_TOKENS.get(slicer_choice)
    if not slicer:
        raise IntakeError(f"Profiles for '{slicer_choice}' are added by hand for now – a maintainer will "
                          "check the file format and add it manually.")
    allowed = lib.SLICERS[slicer][1]
    brand, model = printer_location(need("Printer brand"), need("Printer model"))
    material = material_name(need("Material type"), need("3DTrcek product name"))
    nozzle = nozzle_name(need("Nozzle diameter"), f.get("Nozzle type", ""))
    login = issue["user"]["login"]
    author = slug(f.get("Credit name", "")) or slug(login)
    if author.lower() == "3dtrcek":
        author = slug(login)

    url, original_name = attachment_url(need("Profile file"))
    raw = workdir / "download"
    if local_file:
        raw.write_bytes(local_file.read_bytes())
    else:
        download(url, raw)
    src, ext = pick_profile_file(raw, original_name, allowed, workdir)

    folder = lib.PROFILES / brand / model
    base = f"3DTrcek_{material}_{model}_{nozzle}_{slicer}_by-{author}"
    target = folder / f"{base}{ext}"
    n = 2
    while target.exists():
        target = folder / f"{base}-{n}{ext}"
        n += 1

    folder.mkdir(parents=True, exist_ok=True)
    target.write_bytes(src.read_bytes())

    _, errors, warnings = lib.parse(target)
    _, _, gcode = safety.scan_file(target, target.name)
    if errors:
        target.unlink()
        raise IntakeError("The file didn't pass the checks:\n" + "\n".join(f"- {e}" for e in errors))

    return {
        "number": issue["number"], "login": login, "user_id": issue["user"]["id"],
        "path": target.relative_to(ROOT).as_posix(), "material": material.replace("-", " "),
        "printer": f"{brand.replace('-', ' ').title()} {model.replace('-', ' ')}",
        "slicer": lib.SLICERS[slicer][0], "nozzle": nozzle, "warnings": warnings, "gcode": gcode,
    }


def sh(*args: str) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout.strip()


def comment(number: int, text: str) -> None:
    sh("gh", "issue", "comment", str(number), "--body", text)


def publish(r: dict) -> None:
    branch = f"profile/issue-{r['number']}"
    title = f"Add {r['material']} profile for {r['printer']} ({r['slicer']})"
    sh("git", "config", "user.name", "3DTrcek")
    sh("git", "config", "user.email", "info@3dtrcek.com")
    sh("git", "checkout", "-B", branch)
    sh("git", "add", r["path"])
    sh("git", "commit", "-m", f"{title}\n\nSubmitted in #{r['number']} by @{r['login']}.\n\n"
       f"Co-authored-by: {r['login']} <{r['user_id']}+{r['login']}@users.noreply.github.com>")
    sh("git", "push", "--force", "origin", branch)
    warn = ("\n\n**Warnings:**\n" + "\n".join(f"- {w}" for w in r["warnings"])) if r["warnings"] else ""
    if r["gcode"]:
        warn += ("\n\n**⚠️ Custom G-code in this profile – read it before merging:**\n```gcode\n"
                 + "\n".join(r["gcode"][:200]) + "\n```")
    else:
        warn += "\n\n✅ Safety scan: no custom G-code, no post-processing scripts."
    body = (f"Profile submitted by @{r['login']} in #{r['number']}.\n\n"
            f"| | |\n|---|---|\n| Material | {r['material']} |\n| Printer | {r['printer']} |\n"
            f"| Nozzle | {r['nozzle']} |\n| Slicer | {r['slicer']} |\n| File | `{r['path']}` |"
            f"{warn}\n\nMerging adds it to the catalog automatically.\n\nCloses #{r['number']}")
    existing = sh("gh", "pr", "list", "--head", branch, "--json", "url", "--jq", ".[0].url")
    pr_url = existing or sh("gh", "pr", "create", "--head", branch, "--title", title, "--body", body)
    comment(r["number"], f"Thanks @{r['login']}! 🎉 Your profile has been prepared as {pr_url} – "
                         f"it will appear in the [catalog](https://github.com/{lib.REPO}/blob/main/CATALOG.md) as soon as it's merged.")


def main(argv: list[str]) -> int:
    dry = "--dry-run" in argv
    args = [a for a in argv if not a.startswith("--")]
    event_path = Path(args[0]) if args else Path(os.environ["GITHUB_EVENT_PATH"])
    local = Path(args[1]) if len(args) > 1 else None
    event = json.loads(event_path.read_text(encoding="utf-8"))
    number = event["issue"]["number"]

    with tempfile.TemporaryDirectory() as tmp:
        try:
            result = build(event, local, Path(tmp))
        except (IntakeError, zipfile.BadZipFile, OSError) as e:
            msg = (f"🤖 I couldn't prepare this profile automatically:\n\n{e}\n\n"
                   "A maintainer can fix the form fields or the attachment and re-add the `approved` label.")
            print(msg)
            if not dry:
                comment(number, msg)
                sh("gh", "issue", "edit", str(number), "--remove-label", "approved")
            return 1

    print(json.dumps(result, indent=2))
    if not dry:
        publish(result)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
