# Contributing a profile

Thanks for helping grow the library! A good profile saves other people hours of tuning.

**Easiest way:** use the [submission form](../../issues/new/choose) — no Git needed. We rename the file and put it in the right place for you. The rest of this page is for people who prefer to open a pull request.

## What we accept

- Profiles for **3DTrcek filaments** — any material, including new ones.
- One file = one material + one printer + one nozzle size + one slicer.
- Profiles you have **actually printed with** — at least a calibration cube and one real part.

| Slicer | File name token | File |
|---|---|---|
| Bambu Studio | `BambuStudio` | `.json` |
| OrcaSlicer | `OrcaSlicer` | `.json` |
| Creality Print | `CrealityPrint` | `.json` |
| QIDI Studio | `QIDIStudio` | `.json` |
| ElegooSlicer | `ElegooSlicer` | `.json` |
| Anycubic Slicer Next | `AnycubicSlicerNext` | `.json` |
| PrusaSlicer | `PrusaSlicer` | `.ini` |
| SuperSlicer | `SuperSlicer` | `.ini` |
| UltiMaker Cura | `Cura` | `.curaprofile` |
| Simplify3D | `Simplify3D` | `.fff` |
| FlashPrint | `FlashPrint` | `.zip` / `.cfg` |
| ideaMaker | `ideaMaker` | `.zip` / `.data` / `.bin` |
| anything else | `Other` | `.zip` |

## Where to put it

```
profiles/<brand>/<model>/
```

- **brand** — lowercase, dashes: `bambu-lab`, `prusa`, `creality`, `elegoo`, `qidi`, `voron`…
- **model** — no spaces: `MK4S`, `Ender-3-V3`, `K1-Max`, `X1-P1`

Create the folders if your printer isn't there yet — that's how the library grows. Please check the [catalog](CATALOG.md) first so the same printer doesn't end up under two names.

## File naming

```
3DTrcek_<Material>_<Printer>_<Nozzle>_<Slicer>_by-<YourName>.<ext>
```

Examples:

```
profiles/prusa/MK4S/3DTrcek_PETG-Mat_MK4S_0.4_PrusaSlicer_by-janez.ini
profiles/creality/K1-Max/3DTrcek_PLA-Silk_K1-Max_0.4_CrealityPrint_by-maker42.json
profiles/voron/2.4/3DTrcek_ASA-CF_2.4_0.6-HF-HS_OrcaSlicer_by-anna.json
```

- `-` inside a part, `_` between parts. No spaces, no brackets.
- **Material** — product name as on the spool or in the shop, dashes instead of spaces: `PLA-Mat-HS`, `PETG-Mat`, `ASA-CF`.
- **Printer** — same as the model folder.
- **Nozzle** — diameter in mm; add `-HF` for high-flow, `-HS` for hardened steel.
- **Slicer** — a token from the table above.
- `by-3DTrcek` is reserved for official profiles.
- Inside the slicer, give the preset the same name (without the extension) so people recognise it after import.

## Automatic checks

Every pull request is checked for file type, file name, folder and (for `.json`) valid content. If something's off, the PR page tells you what to fix. After merging, the [catalog](CATALOG.md) updates itself.

## Review

A 3DTrcek team member reviews every submission, usually within a week. We may rename the file or ask a question. You're credited in the file name and the catalog.
