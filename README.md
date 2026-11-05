# 3DTrček Filament Profiles

Slicer profiles for **[3DTrček](https://3dtrcek.com)** filaments — made in Europe, compounded, extruded and spooled in-house in Ljubljana, Slovenia.

This library has two parts:

| Folder | Who makes it | What it means |
|---|---|---|
| [`official/`](official/) | 3DTrček team | Tuned and tested by us on our own printers. Start here if your printer is listed. |
| [`community/`](community/) | 3DTrček users | Shared by customers for printers we don't run ourselves. Tested by the person who submitted it — check the notes in each folder. |

**Got a printer we don't cover? Share your profile** — see [How to contribute](#how-to-contribute). Every profile you add helps the next person print right the first time.

---

## Official profiles

| Printer | Slicer | Folder |
|---|---|---|
| Bambu Lab H2S | Bambu Studio / OrcaSlicer | [`official/bambu-lab/H2S`](official/bambu-lab/H2S) |
| Bambu Lab X1 / X1C / P1S / P1P | Bambu Studio / OrcaSlicer | [`official/bambu-lab/X1-P1`](official/bambu-lab/X1-P1) |

## Community profiles

Browse [`community/`](community/) by printer brand. Each profile is named so you can see the material, printer, nozzle and who shared it at a glance.

---

## How to install a profile

### Bambu Studio
1. Download the `.json` file (open it on GitHub → **Download raw file** button).
2. In Bambu Studio: **File → Import → Import Configs…** and select the file.
3. The profile appears in the filament dropdown under **User presets**.
4. Select it for the AMS slot / external spool you're using.

### OrcaSlicer
1. Download the `.json` file.
2. **File → Import → Import Configs…**
3. Pick it in the filament list. If it doesn't show, click the gear next to the filament list and make sure the profile is enabled for your printer.

> **Tip:** Profiles that start with `inherits` are based on a system preset (e.g. *Generic PLA*). Your slicer needs that base preset installed for the printer — it is by default for supported printers.

### Download everything at once
Click the green **Code → Download ZIP** button at the top of this page.

---

## How to contribute

You don't need to know Git. Pick whichever way is easier:

### Option A — Submission form (easiest)
1. Go to **[Issues → New issue → Submit a filament profile](../../issues/new/choose)**.
2. Fill in the form and drag your exported `.json` file into the upload box.
3. We review it and add it to the library, crediting you.

### Option B — Pull request (for GitHub users)
1. Fork this repository.
2. Put your file in the right `community/<brand>/` folder using the [naming rule](CONTRIBUTING.md#file-naming).
3. Open a pull request and fill in the checklist.

Full rules: **[CONTRIBUTING.md](CONTRIBUTING.md)**

### How to export your profile
- **Bambu Studio / OrcaSlicer:** select your filament preset → **File → Export → Export Configs…** → tick only your filament preset → save the `.json`.

---

## Disclaimer

Profiles are a starting point. Printers, nozzles, enclosures and room conditions differ — always run a temperature tower and flow test for best results. Community profiles are shared by users and are not tested by 3DTrček unless marked otherwise.

Questions about a material? Every product page on [3dtrcek.com](https://3dtrcek.com) has the technical data sheet, or contact us at info@3dtrcek.com.

## License

Profiles are shared under [CC BY 4.0](LICENSE) — free to use, share and modify, with credit to the author.
