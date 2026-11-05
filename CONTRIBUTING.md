# Contributing a profile

Thanks for helping grow the library! A good profile saves other people hours of tuning.

## What we accept

- Profiles for **3DTrcek filaments only** (any material from 3dtrcek.com).
- Exported filament presets from any slicer:

  | Slicer | File |
  |---|---|
  | Bambu Studio, OrcaSlicer, Creality Print, QIDI Studio, ElegooSlicer, Anycubic Slicer Next | `.json` |
  | PrusaSlicer, SuperSlicer | `.ini` |
  | UltiMaker Cura | `.curaprofile` |
  | Simplify3D | `.fff` |

  Using a slicer that's not listed (FlashPrint, ideaMaker…)? Submit it through the form anyway and we'll work out the format with you.
- One profile = one material + one printer + one nozzle size.
- Profiles you have **actually printed with** — at least a calibration cube and one real part.

We don't accept profiles for official printers that only change cosmetic things like the preset name. If you improved an official profile, open an issue and tell us what you changed — we'll test it.

## File naming

```
3DTrcek_<Material>_<Printer>_<Nozzle>_by-<YourName>.<ext>
```

Examples:

```
3DTrcek_PETG-Mat_Prusa-MK4S_0.4_by-janez.json
3DTrcek_PLA-Silk_Ender-3-V3_0.4_by-maker42.json
3DTrcek_ASA-CF_Voron-2.4_0.6-HF_by-anna.json
```

Rules:
- Use `-` inside a part, `_` between parts. No spaces, no brackets.
- **Material** = name as on 3dtrcek.com (`PLA`, `PLA-Mat`, `PLA-Mat-HS`, `PLA-Silk`, `PETG`, `PETG-Mat`, `ASA`, `ASA-CF`, `TPU`, `PBT`…). Add `-Mix` for Mix/Outlet spools if you tuned specifically for them.
- **Nozzle** = diameter in mm; add `-HF` for high-flow nozzles, `-HS` for hardened steel if it matters.
- Inside the slicer, set the preset name to the same thing (without the extension), so people recognise it after import.

## Where to put it

```
community/<brand>/<model>/your-file.json
```

Use an existing folder if there is one. If your printer isn't there, create a folder named like `community/prusa/MK4S`. If unsure, use `community/other/`.

## Pull request checklist

When you open a PR, the template asks for:

- [ ] Printer model, nozzle, and any mods (enclosure, hotend swap, firmware)
- [ ] Slicer and version
- [ ] Filament colour / batch you tested with (if you know it)
- [ ] Key settings: nozzle temp, bed temp, max volumetric speed, flow ratio, pressure advance
- [ ] What you printed with it and how it went (photos welcome!)
- [ ] I agree to share this profile under CC BY 4.0

## Automatic checks

Every PR is checked automatically for:
- valid JSON (for `.json` files)
- correct file name
- correct folder (`community/…` — the `official/` folder is maintained by 3DTrcek only)

If a check fails, the PR page tells you what to fix.

## Review

A 3DTrcek team member reviews every submission, usually within a week. We may ask a question or rename the file. Once merged, you're credited in the file name and in the commit history.
