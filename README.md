# FGC Part Library — Fusion 360 Add-In

Search the **2026 FIRST Global Challenge** kit by **name** (not part number) and insert
the matching REV STEP part into your active Fusion design. Each result shows how many
of that part your team is **allotted** (from the official BOM) and how many you've
already **placed in the current design**.

## Install / Enable

The add-in is already in your Fusion AddIns folder:

```
%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns\FGCPartLibrary\
```

1. Open Fusion 360.
2. Go to **Utilities → Add-Ins → Scripts and Add-Ins** (or press **Shift+S**).
3. Open the **Add-Ins** tab, select **FGCPartLibrary**, and click **Run**.
   Tick **Run on Startup** so it loads automatically next time.
4. The **FGC Part Library** panel opens (docked on the right). You can also reopen it
   from **Design workspace → Add-Ins panel → FGC Part Library**.

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
