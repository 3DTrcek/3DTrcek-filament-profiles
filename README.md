# 3DTrcek Filament Profiles

Slicer profiles for **[3DTrcek](https://3dtrcek.com)** filaments — made in Europe, compounded, extruded and spooled in-house in Ljubljana, Slovenia.

## 🔎 Find your profile

### 👉 **[Open the profile catalog](CATALOG.md)**

The catalog lists every profile by printer, with material, nozzle and slicer — press <kbd>Ctrl</kbd>+<kbd>F</kbd> and type your printer. It updates automatically whenever a profile is added.

- ⭐ **Official** profiles are tuned and tested by the 3DTrcek team.
- Other profiles are shared by users and tested by the person who submitted them.

**Your printer isn't there?** Start from your slicer's generic preset for the same material, use the temperatures from the data sheet on [3dtrcek.com](https://3dtrcek.com) — and once it prints well, [share it](../../issues/new/choose) so the next person doesn't start from zero.

---

## How to install a profile

### Bambu Studio
1. Download the `.bbsflmt` (preset bundle) or `.json` file from the [catalog](CATALOG.md) (⬇ link).
2. In Bambu Studio: **File → Import → Import Configs…** and select the file.
3. The profile appears in the filament dropdown under **User presets**.
4. Select it for the AMS slot / external spool you're using.

### OrcaSlicer
1. Download the `.orca_filament` (preset bundle) or `.json` file.
2. **File → Import → Import Configs…**
3. Pick it in the filament list. If it doesn't show, click the gear next to the filament list and make sure the profile is enabled for your printer.

> **Tip:** Profiles that start with `inherits` are based on a system preset (e.g. *Generic PLA*). Your slicer needs that base preset installed for the printer — it is by default for supported printers.

### Creality Print / QIDI Studio / ElegooSlicer / Anycubic Slicer Next
These are based on OrcaSlicer — use **File → Import → Import Configs…** and pick the `.json` file.

### PrusaSlicer / SuperSlicer
**File → Import → Import Config…** and pick the `.ini` file. The filament preset appears in the Filament tab.

### UltiMaker Cura
**Preferences → Configure Cura → Profiles → Import** and pick the `.curaprofile` file.

### FlashPrint / Simplify3D / ideaMaker
Unzip the download if needed and import it through the slicer's filament/material profile import.

### Download everything at once
Click the green **Code → Download ZIP** button at the top of this page.

---

## How to contribute

You don't need to know Git. Pick whichever way is easier:

### Option A — Submission form (easiest)
1. Go to **[Issues → New issue → Submit a filament profile](../../issues/new/choose)**.
2. Pick your slicer, printer and material, and drag your exported profile file into the upload box.
3. We review it and add it to the library, crediting you.

### Option B — Pull request (for GitHub users)
1. Fork this repository.
2. Put your file in `profiles/<brand>/<model>/` using the [naming rule](CONTRIBUTING.md#file-naming).
3. Open a pull request and fill in the checklist.

Full rules: **[CONTRIBUTING.md](CONTRIBUTING.md)**

### How to export your profile
- **Bambu Studio / OrcaSlicer and Orca-based slicers:** select your filament preset → **File → Export → Export Configs…** → tick only your filament preset → save the `.json`.
- **PrusaSlicer / SuperSlicer:** **File → Export → Export Config…** → save the `.ini`.
- **UltiMaker Cura:** **Preferences → Configure Cura → Profiles** → select your profile → **Export**.

---

## 🛡️ Safety

Slicer profiles are plain settings files, but two things inside them could be misused, so every file is scanned automatically before it can be added:

- **No programs.** Profiles that would run a post-processing script or program on your computer are rejected. Files must be plain text (or a slicer bundle of plain-text files) – no executables, no binaries.
- **No dangerous G-code.** Commands that could damage a printer or change its stored settings – firmware updates, factory resets, writing to EEPROM, disabling endstops, changing Z offset or steps/mm, temperatures above safe limits – are blocked. Any other unusual custom G-code is shown to a 3DTrcek maintainer, who reads it before approving.
- **Human review.** Nothing is added without a 3DTrcek team member approving it.
- **Issues and comments are guarded too.** Anyone can attach a file to an issue, so every attachment from outside the team is scanned the same way; anything that fails is removed immediately, and links to unknown websites are flagged for review.

> **Only download profiles from the [catalog](CATALOG.md)** – never from issues, comments or links someone sends you.

Found something suspicious? [Open an issue](../../issues/new) or email info@3dtrcek.com.

## Disclaimer

Profiles are a starting point. Printers, nozzles, enclosures and room conditions differ — always run a temperature tower and flow test for best results. Profiles shared by users are not tested by 3DTrcek unless marked ⭐ official.

Questions about a material? Every product page on [3dtrcek.com](https://3dtrcek.com) has the technical data sheet, or contact us at info@3dtrcek.com.

## License

Profiles are shared under [CC BY 4.0](LICENSE) — free to use, share and modify, with credit to the author.
