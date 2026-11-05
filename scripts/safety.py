"""Safety scan for slicer profiles.

Two real risks with shared slicer profiles:

1. Post-processing scripts. PrusaSlicer, SuperSlicer, OrcaSlicer and Bambu Studio can run an
   arbitrary program on the user's computer after slicing ("post_process"). A profile that sets
   one could run malware. -> always blocked.

2. Custom G-code. Filament profiles may carry start/end G-code. Most of it is harmless
   (chamber temperature, fan, pressure advance), but some commands can damage a printer or
   silently change its stored configuration. -> dangerous commands are blocked, any other
   custom G-code is reported so a human looks at it before merging.

Files must also be plain text (or a zip of plain-text files for formats that are zips).
"""
from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

MAX_MEMBER = 2 * 1024 * 1024
MAX_MEMBERS = 50
TEXT_MEMBER_EXT = {".json", ".ini", ".cfg", ".fff", ".txt", ".xml", ""}  # "" = Cura profile parts

NOZZLE_MAX = 320   # °C
BED_MAX = 130      # °C
CHAMBER_MAX = 80   # °C

# command -> reason. Matched at the start of a G-code line (case-insensitive).
BLOCKED = {
    "M500": "writes settings to the printer's permanent memory (EEPROM)",
    "M502": "resets the printer to factory settings",
    "M997": "starts a firmware update",
    "M30": "deletes a file from the SD card",
    "M28": "writes a file to the SD card",
    "M29": "writes a file to the SD card",
    "M121": "disables endstops",
    "M211": "changes software endstops",
    "M92": "changes steps/mm",
    "M206": "changes home offsets",
    "M851": "changes the probe Z offset",
    "M301": "changes hotend PID tuning",
    "M304": "changes bed PID tuning",
    "M303": "runs PID autotune",
    "M907": "changes motor currents",
    "M906": "changes motor currents",
    "SAVE_CONFIG": "rewrites the Klipper configuration",
    "SET_KINEMATIC_POSITION": "overrides the printer's known position",
    "FORCE_MOVE": "moves motors without homing or limits",
    "SDCARD_RESET_FILE": "manipulates SD card files",
    "DELETE_FILE": "deletes files",
}
TEMP_LIMITS = {"M104": NOZZLE_MAX, "M109": NOZZLE_MAX, "M140": BED_MAX, "M190": BED_MAX,
               "M141": CHAMBER_MAX, "M191": CHAMBER_MAX}
POST_PROCESS = re.compile(r"post_?process", re.I)
SETTING_TEMP_KEYS = {
    "nozzle_temperature": NOZZLE_MAX, "nozzle_temperature_initial_layer": NOZZLE_MAX,
    "temperature": NOZZLE_MAX, "first_layer_temperature": NOZZLE_MAX,
    "hot_plate_temp": BED_MAX, "textured_plate_temp": BED_MAX, "cool_plate_temp": BED_MAX,
    "eng_plate_temp": BED_MAX, "bed_temperature": BED_MAX, "first_layer_bed_temperature": BED_MAX,
}


def _is_text(data: bytes) -> bool:
    if b"\x00" in data:
        return False
    try:
        data.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def _values(v) -> list[str]:
    if isinstance(v, list):
        return [x for x in v if isinstance(x, str)]
    return [v] if isinstance(v, str) else []


def _settings(text: str, ext: str) -> list[tuple[str, str]]:
    """Extract (key, value) pairs from a JSON preset or an INI/CFG file."""
    pairs: list[tuple[str, str]] = []
    if ext == ".json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return pairs
        if isinstance(data, dict):
            for k, v in data.items():
                pairs += [(k, s) for s in _values(v)]
        return pairs
    for line in text.splitlines():
        if "=" in line and not line.lstrip().startswith(("#", ";", "[")):
            k, _, v = line.partition("=")
            pairs.append((k.strip(), v.strip()))
    return pairs


def _gcode_lines(value: str) -> list[str]:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        value = value[1:-1]
    value = value.replace("\\n", "\n")
    out = []
    for raw in value.splitlines():
        line = raw.split(";", 1)[0].strip()
        if line:
            out.append(line)
    return out


# Commands that are routine in filament start/end G-code and need no human review.
SAFE = {"M104", "M109", "M140", "M190", "M141", "M191", "M106", "M107", "M142", "M900", "M572",
        "M220", "M221", "M73", "G4", "M117", "SET_PRESSURE_ADVANCE", "SET_FAN_SPEED",
        "SET_HEATER_TEMPERATURE", "TEMPERATURE_WAIT", "M204", "M205"}
TEMPLATE = re.compile(r"\{[^{}]*\}")


def _commands(line: str) -> list[str]:
    """Strip slicer template logic ({if …}, {endif}) and return the remaining G-code commands."""
    code = TEMPLATE.sub(" ", line).strip()
    return [c for c in re.split(r"\s*\n\s*", code) if c]


def needs_review(lines: list[str]) -> list[str]:
    out = []
    for line in lines:
        for cmd in _commands(line):
            if cmd.split()[0].upper() not in SAFE:
                out.append(line)
                break
    return out


def _check_gcode(lines: list[str], where: str, errors: list[str]) -> None:
    for raw in lines:
        for line in _commands(raw):
            cmd = line.split()[0].upper()
            if cmd in BLOCKED:
                errors.append(f"{where}: G-code '{line}' is not allowed – it {BLOCKED[cmd]}")
            elif cmd in TEMP_LIMITS:
                m = re.search(r"\bS(\d+(?:\.\d+)?)", line, re.I)
                if m and float(m.group(1)) > TEMP_LIMITS[cmd]:
                    errors.append(f"{where}: '{line}' sets a temperature above {TEMP_LIMITS[cmd]} °C")


def scan_text(text: str, ext: str, where: str) -> tuple[list[str], list[str], list[str]]:
    """Return (errors, warnings, custom_gcode_lines)."""
    errors: list[str] = []
    warnings: list[str] = []
    gcode: list[str] = []

    pairs = _settings(text, ext)
    if pairs:
        for key, value in pairs:
            if POST_PROCESS.search(key) and value.strip() not in ("", '""', "[]"):
                errors.append(f"{where}: '{key}' runs a program on the user's computer – not allowed in shared profiles")
            elif "gcode" in key.lower():
                lines = _gcode_lines(value)
                if lines:
                    _check_gcode(lines, f"{where} [{key}]", errors)
                    gcode += [f"{key}: {ln}" for ln in lines]
            elif key in SETTING_TEMP_KEYS:
                for num in re.findall(r"\d+(?:\.\d+)?", value):
                    if float(num) > SETTING_TEMP_KEYS[key]:
                        errors.append(f"{where}: {key} = {value} is above {SETTING_TEMP_KEYS[key]} °C")
                        break
    else:
        # unknown structure (e.g. Simplify3D XML): scan every line
        if POST_PROCESS.search(text):
            warnings.append(f"{where}: mentions post-processing – check it by hand")
        lines = [ln for ln in _gcode_lines(text) if re.match(r"^(?:[GM]\d+|[A-Z_]{4,})\b", ln)]
        _check_gcode(lines, where, errors)

    review = needs_review([g.split(": ", 1)[1] for g in gcode])
    if review:
        warnings.append(f"{where}: contains {len(review)} line(s) of unusual custom G-code – review before merging")
    gcode = [g for g in gcode if g.split(": ", 1)[1] in review]
    return errors, warnings, gcode


def scan_file(path: Path, rel: str) -> tuple[list[str], list[str], list[str]]:
    """Safety-scan a profile file (plain text or zip). Return (errors, warnings, gcode_lines)."""
    data = path.read_bytes()
    ext = path.suffix.lower()

    if zipfile.is_zipfile(path):
        errors: list[str] = []
        warnings: list[str] = []
        gcode: list[str] = []
        with zipfile.ZipFile(path) as z:
            infos = [i for i in z.infolist() if not i.is_dir()]
            if len(infos) > MAX_MEMBERS:
                return [f"{rel}: archive has too many files ({len(infos)})"], [], []
            for info in infos:
                name = info.filename
                mext = Path(name).suffix.lower()
                where = f"{rel} → {name}"
                if name.startswith("__MACOSX/"):
                    continue
                if mext not in TEXT_MEMBER_EXT:
                    errors.append(f"{where}: file type '{mext}' is not allowed inside a profile archive")
                    continue
                if info.file_size > MAX_MEMBER:
                    errors.append(f"{where}: too large when unpacked ({info.file_size} bytes)")
                    continue
                content = z.read(info)
                if not _is_text(content):
                    errors.append(f"{where}: not a plain-text file")
                    continue
                e, w, g = scan_text(content.decode("utf-8"), mext, where)
                errors += e
                warnings += w
                gcode += g
        return errors, warnings, gcode

    if not _is_text(data):
        return [f"{rel}: not a plain-text file – profiles must be readable text"], [], []
    return scan_text(data.decode("utf-8"), ext, rel)
