# FGC Part Library — Fusion 360 Add-In

Search the **2026 FIRST Global Challenge** kit by **name** (not part number) and insert
the matching REV STEP part into your active Fusion design. Each result shows how many
of that part your team is **allotted** (from the official BOM) and how many you've
already **placed in the current design**.

## Setup on a new machine

The add-in loads STEP files from its own bundled `parts/` folder, so it is fully
self-contained — no extra downloads. You just need the `FGCPartLibrary` folder to end
up inside Fusion's **AddIns** folder:

- **Windows:** `%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns\`
- **macOS:** `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/`

The final path must be `…/AddIns/FGCPartLibrary/FGCPartLibrary.py` (the folder must be
named exactly **FGCPartLibrary**, not nested one level deeper).

### Method A — clone with Git (recommended; easy to update later)

Open a terminal and clone straight into the AddIns folder:

```bash
# Windows (PowerShell / Terminal)
cd "$env:APPDATA\Autodesk\Autodesk Fusion 360\API\AddIns"
git clone https://github.com/mxnviir/FGCPartLibrary.git

# macOS / Linux
cd "$HOME/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns"
git clone https://github.com/mxnviir/FGCPartLibrary.git
```

To pull future updates later: `cd` into that folder and run `git pull`.

### Method B — download the ZIP (no Git needed)

1. Go to <https://github.com/mxnviir/FGCPartLibrary> → green **Code** button → **Download ZIP**.
2. Unzip it. GitHub names the folder `FGCPartLibrary-main` — **rename it to `FGCPartLibrary`**.
3. Move that `FGCPartLibrary` folder into the AddIns folder shown above.

### Then enable it in Fusion

1. Open Fusion 360.
2. Go to **Utilities → Add-Ins → Scripts and Add-Ins** (or press **Shift+S**).
3. Open the **Add-Ins** tab, select **FGCPartLibrary**, and click **Run**.
   Tick **Run on Startup** so it loads automatically next time.
4. The **FGC Part Library** panel opens (docked on the right). You can also reopen it
   from **Design workspace → Add-Ins panel → FGC Part Library**.

> **Note:** the `catalog.json` includes a `library_path` fallback pointing at the
> original author's Downloads folder. You can ignore it — the add-in uses the bundled
> `parts/` folder first. It only matters if you delete `parts/` and want to point at an
> external STEP folder instead.

## How to use

- Type in the search box to filter by name, part number, or category
  (e.g. `motor`, `bracket 90`, `gearbox`, `REV-41-1600`). Multiple words all must match.
- **Allotted** = the "Total QTY (packs)" your team gets per the BOM.
  The badge shows how many you've inserted so far (turns amber when you hit the limit,
  red if you exceed it).
- Click **Insert** to import the part. Most parts come in as a named **component**
  (tagged `COMP` in the list). Parts you list in `body_import_names.txt` (extrusions,
  C channels, etc.) come in as loose **bodies** (tagged `BODY`), not grounded, so you
  can move them freely. When a part has more than one model (e.g. the UltraPlanetary
  "with 2 Cartridges" or the "Simple" variants), pick the file from the dropdown first.

### Choosing which parts import as bodies

Edit **`body_import_names.txt`** in this folder. Any part whose name or part number
contains a line you add is imported as bodies; everything else stays a component.
Matching is case-insensitive substring (e.g. `Extrusion`, `C Channel`, or a specific
part number like `REV-41-1762`). Changes apply on the next insert — click **Refresh**
to update the `BODY`/`COMP` tags shown in the list. It ships pre-filled with
`Extrusion` and `C Channel`.
- **Refresh counts** re-scans the design (use it after deleting components).
- **Open folder** opens the STEP library in Explorer.

## Data & files

- `catalog.json` — generated from `2026 FGC Bill of Materials.pdf` + the STEP folder.
  - 155 kit entries; 115 have CAD (cables, screws, zipties and other consumables have
    no STEP file — toggle **"Only parts with CAD"** off to see them all).
  - **If you move the STEP folder**, edit `"library_path"` in `catalog.json` to the new
    location, then disable/enable the add-in (or click Refresh).
- `FGCPartLibrary.py` — add-in logic (loads catalog, opens palette, imports STEP).
- `palette.html` — the search UI.

## Notes

- Counting works for both import modes: component-mode inserts are counted by the
  component name the add-in assigns (`REV-xx-xxxx | Name`), and body-mode inserts are
  counted via a hidden tag on each body (counted per-insert, and self-correcting when
  you delete bodies). Parts you insert manually won't be counted.
- The allotted quantity is per **pack** as listed in the BOM — e.g. "M3 x 8mm Hex Cap
  Screws - 100 Pack, QTY 8" means 8 packs allotted, not 8 screws.
