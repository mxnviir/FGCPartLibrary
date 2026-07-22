# FGC Part Library - Fusion 360 Add-In
# Search the 2026 FGC kit by NAME (not part number) and insert REV STEP parts.
# Shows how many of each part your team is allotted (from the official BOM) and
# how many you've already placed in the current design.

import adsk.core
import adsk.fusion
import traceback
import os
import json
import uuid

# ---------------------------------------------------------------------------
# Globals kept alive for the lifetime of the add-in
# ---------------------------------------------------------------------------
_app = None
_ui = None
_handlers = []          # keep event handlers referenced so they aren't GC'd
_palette = None

CMD_ID = 'FGCPartLibraryShow'
PALETTE_ID = 'FGCPartLibraryPalette'
PALETTE_NAME = 'FGC Part Library'
PANEL_ID = 'SolidScriptsAddinsPanel'

ATTR_GROUP = 'FGCPartLibrary'   # attribute group used to tag/count body-imported parts

_ADDIN_DIR = os.path.dirname(os.path.realpath(__file__))
_CATALOG_PATH = os.path.join(_ADDIN_DIR, 'catalog.json')
_BODY_NAMES_PATH = os.path.join(_ADDIN_DIR, 'body_import_names.txt')
_catalog = None


# ---------------------------------------------------------------------------
# "Import as bodies" rules
# ---------------------------------------------------------------------------
def load_body_keywords():
    """Read body_import_names.txt fresh each call so edits take effect without a
    reload. Returns a list of lowercased match terms. Blank lines and lines
    starting with '#' are ignored.
    """
    terms = []
    try:
        with open(_BODY_NAMES_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                s = line.strip()
                if s and not s.startswith('#'):
                    terms.append(s.lower())
    except Exception:
        pass
    return terms


def imports_as_body(part, name):
    """True if this part should be imported as loose bodies (name or part number
    contains any configured term); otherwise it is imported as a component.
    """
    hay = '{} {}'.format(part or '', name or '').lower()
    return any(term in hay for term in load_body_keywords())


# ---------------------------------------------------------------------------
# Catalog helpers
# ---------------------------------------------------------------------------
def load_catalog():
    global _catalog
    with open(_CATALOG_PATH, 'r', encoding='utf-8') as f:
        _catalog = json.load(f)
    return _catalog


def resolve_file_path(filename):
    """Return the absolute path to a STEP file.

    Prefers STEP files bundled inside the add-in (the 'parts' subfolder) so the
    add-in is portable across devices. Falls back to an external 'library_path'
    if one is set in catalog.json and the bundled file is not present.
    """
    subdir = _catalog.get('library_subdir', 'parts')
    bundled = os.path.join(_ADDIN_DIR, subdir, filename)
    if os.path.exists(bundled):
        return os.path.normpath(bundled)
    lib = _catalog.get('library_path', '')
    if lib:
        return os.path.normpath(os.path.join(lib, filename))
    return os.path.normpath(bundled)


def count_usage():
    """Count how many of each part are in the active design, keyed by part base
    (e.g. 'REV-41-1300'). Handles both import modes:

    - Component-mode inserts create a named occurrence ("REV-41-1300 | Name"); we
      count occurrences (anywhere in the tree) whose name matches that format.
    - Body-mode inserts tag every body with a shared 'gid' attribute; we count
      distinct gids per part (a part made of many bodies counts once), skipping
      attributes whose body has been deleted so the count stays accurate.

    A given part only ever uses one mode, so the two tallies never double-count.
    """
    counts = {}
    try:
        design = adsk.fusion.Design.cast(_app.activeProduct)
        if not design:
            return counts
        root = design.rootComponent

        # Component-mode: occurrences named "REV-xx-xxxx | Name" (the ' | ' marker
        # avoids matching a STEP's own internal sub-component names).
        for occ in root.allOccurrences:
            name = occ.component.name or ''
            if ' | ' in name:
                token = name.split(' ')[0]
                if token.startswith('REV-'):
                    counts[token] = counts.get(token, 0) + 1

        # Body-mode: distinct gids from live (non-deleted) tagged bodies.
        seen = {}
        for attr in design.findAttributes(ATTR_GROUP, 'gid'):
            parent = attr.parent
            if parent is None:
                continue
            try:
                if not parent.isValid:
                    continue
            except Exception:
                pass
            try:
                token, gid = attr.value.split('||', 1)
            except ValueError:
                continue
            seen.setdefault(token, set()).add(gid)
        for token, gids in seen.items():
            counts[token] = counts.get(token, 0) + len(gids)
    except Exception:
        pass
    return counts


def build_payload():
    """Everything the HTML palette needs on load / refresh."""
    return json.dumps({
        'library_name': _catalog.get('library_name', ''),
        'library_path': _catalog.get('library_path', ''),
        'parts': _catalog.get('parts', []),
        'usage': count_usage(),
        'body_keywords': load_body_keywords(),
    })


# ---------------------------------------------------------------------------
# STEP import
# ---------------------------------------------------------------------------
def _add_new_component():
    """Add an empty component/occurrence to the active design's root.

    These REV STEP files are multi-component assemblies, so they can only be
    inserted into an assembly-capable document. A Fusion *Part* document can hold
    only one component and raises a specific error. In that case we open a fresh
    assembly-capable design document and insert there.

    Returns (occurrence, target_component, note). target_component is where body
    imports should end up (root of whatever document we landed in). note is a
    user-facing string (may be '').
    """
    transform = adsk.core.Matrix3D.create()
    design = adsk.fusion.Design.cast(_app.activeProduct)
    try:
        root = design.rootComponent
        return root.occurrences.addNewComponent(transform), root, ''
    except RuntimeError as e:
        msg = str(e)
        if 'one component' in msg or 'add this Part to an Assembly' in msg:
            # Current doc is a Part document -> spin up an assembly-capable one.
            _app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
            design = adsk.fusion.Design.cast(_app.activeProduct)
            root = design.rootComponent
            occ = root.occurrences.addNewComponent(transform)
            return occ, root, ('\n(Opened a new assembly document — the previous one was a '
                               'single-part document that can\'t hold multiple components.)')
        raise


def _collect_bodies(component):
    """All BRep bodies in a component and every occurrence beneath it (recursive)."""
    bodies = list(component.bRepBodies)
    for occ in component.allOccurrences:
        bodies.extend(list(occ.component.bRepBodies))
    return bodies


def insert_step(filename, part_label):
    """Import a STEP file. Parts whose name/number matches body_import_names.txt are
    brought in as loose BODIES (no wrapper component, not grounded); everything else
    is brought in as a named COMPONENT (the default).

    part_label is "REV-41-1300 | Core Hex Motor" — we split it to get the part
    number and name for the body/component decision.
    """
    design = adsk.fusion.Design.cast(_app.activeProduct)
    if not design:
        return False, 'Open a Fusion design (Design workspace) before inserting parts.'

    full = resolve_file_path(filename)
    if not os.path.exists(full):
        return False, 'File not found:\n{}\n\nCheck the bundled "parts" folder or library_path in catalog.json.'.format(full)

    if ' | ' in part_label:
        part, name = part_label.split(' | ', 1)
    else:
        part, name = part_label, ''
    as_body = imports_as_body(part, name)

    try:
        new_occ, target, note = _add_new_component()
        import_mgr = _app.importManager
        step_opts = import_mgr.createSTEPImportOptions(full)
        import_mgr.importToTarget(step_opts, new_occ.component)

        if not as_body:
            # COMPONENT mode (default): keep the wrapper as one named component.
            new_occ.component.name = part_label
            result = 'Inserted {} (component){}'.format(part_label, note)
        else:
            # BODY mode: move all bodies up into the target component as loose
            # bodies, tag them for counting, then delete the empty wrapper.
            gid = '{}||{}'.format(part, uuid.uuid4().hex)
            moved = 0
            for body in _collect_bodies(new_occ.component):
                nb = body.moveToComponent(target)
                try:
                    nb.name = part_label
                    nb.attributes.add(ATTR_GROUP, 'gid', gid)
                except Exception:
                    pass
                moved += 1
            new_occ.deleteMe()
            if moved == 0:
                return False, 'Imported "{}" but found no solid bodies to place.'.format(part_label)
            result = 'Inserted {} ({} bodies){}'.format(part_label, moved, note)

        try:
            _app.activeViewport.fit()
        except Exception:
            pass
        return True, result
    except Exception:
        return False, 'Import failed:\n{}'.format(traceback.format_exc())


# ---------------------------------------------------------------------------
# Palette HTML event handler (messages from palette.html)
# ---------------------------------------------------------------------------
class PaletteIncomingHandler(adsk.core.HTMLEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            html_args = adsk.core.HTMLEventArgs.cast(args)
            action = html_args.action
            data = {}
            if html_args.data:
                try:
                    data = json.loads(html_args.data)
                except Exception:
                    data = {}

            if action == 'ready' or action == 'refresh':
                html_args.returnData = build_payload()

            elif action == 'insert':
                ok, msg = insert_step(data.get('file', ''), data.get('label', ''))
                html_args.returnData = json.dumps({
                    'ok': ok,
                    'message': msg,
                    'usage': count_usage(),
                })

            elif action == 'openFolder':
                path = _catalog.get('library_path', '')
                if os.path.isdir(path):
                    if os.name == 'nt':
                        os.startfile(path)  # noqa
                html_args.returnData = json.dumps({'ok': True})

            else:
                html_args.returnData = json.dumps({'ok': False, 'message': 'Unknown action'})
        except Exception:
            if _ui:
                _ui.messageBox('Palette handler failed:\n{}'.format(traceback.format_exc()))


class PaletteClosedHandler(adsk.core.UserInterfaceGeneralEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        # Palette closed by user; nothing to persist.
        pass


# ---------------------------------------------------------------------------
# Command that shows/creates the palette
# ---------------------------------------------------------------------------
def show_palette():
    """Create the palette if needed, then dock it right and force it visible.

    Called directly on add-in start and whenever the toolbar button is clicked,
    so it never depends on Command.execute() firing at startup.
    """
    global _palette
    palettes = _ui.palettes
    _palette = palettes.itemById(PALETTE_ID)

    if not _palette:
        # Fusion's embedded browser needs a proper forward-slash file URL.
        # os.path.join gives Windows backslashes which produce a broken
        # "file:///C:/\\Users\\..." URL, so build a real file:// URI.
        html_path = os.path.join(_ADDIN_DIR, 'palette.html')
        html_url = 'file:///' + html_path.replace('\\', '/')
        _palette = palettes.add(
            PALETTE_ID, PALETTE_NAME, html_url,
            True,   # isVisible
            True,   # showCloseButton
            True,   # isResizable
            420, 600  # width, height
        )

        on_incoming = PaletteIncomingHandler()
        _palette.incomingFromHTML.add(on_incoming)
        _handlers.append(on_incoming)

        on_closed = PaletteClosedHandler()
        _palette.closed.add(on_closed)
        _handlers.append(on_closed)

    try:
        _palette.dockingState = adsk.core.PaletteDockingStates.PaletteDockStateRight
    except Exception:
        pass
    _palette.isVisible = True


class ShowPaletteCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            show_palette()
        except Exception:
            if _ui:
                _ui.messageBox('Failed to open palette:\n{}'.format(traceback.format_exc()))


# ---------------------------------------------------------------------------
# Add-in entry points
# ---------------------------------------------------------------------------
def run(context):
    global _app, _ui
    try:
        _app = adsk.core.Application.get()
        _ui = _app.userInterface

        load_catalog()

        # Create (or reuse) the command definition
        cmd_defs = _ui.commandDefinitions
        cmd_def = cmd_defs.itemById(CMD_ID)
        if not cmd_def:
            cmd_def = cmd_defs.addButtonDefinition(
                CMD_ID,
                'FGC Part Library',
                'Search the 2026 FGC kit by name and insert REV parts, with allotted-qty tracking.'
            )

        on_created = ShowPaletteCommandCreatedHandler()
        cmd_def.commandCreated.add(on_created)
        _handlers.append(on_created)

        # Add a button to the ADD-INS panel of the Design workspace
        panel = _ui.allToolbarPanels.itemById(PANEL_ID)
        if panel:
            existing = panel.controls.itemById(CMD_ID)
            if not existing:
                panel.controls.addCommand(cmd_def)

        # Open it immediately so the user sees it on enable. Call show_palette()
        # directly rather than cmd_def.execute(), which does not reliably fire the
        # commandCreated event during add-in startup.
        show_palette()

        adsk.autoTerminate(False)
    except Exception:
        if _ui:
            _ui.messageBox('FGC Part Library failed to start:\n{}'.format(traceback.format_exc()))


def stop(context):
    global _palette
    try:
        # Remove the palette
        if _ui:
            pal = _ui.palettes.itemById(PALETTE_ID)
            if pal:
                pal.deleteMe()
            _palette = None

            # Remove the toolbar button
            panel = _ui.allToolbarPanels.itemById(PANEL_ID)
            if panel:
                ctrl = panel.controls.itemById(CMD_ID)
                if ctrl:
                    ctrl.deleteMe()

            # Remove the command definition
            cmd_def = _ui.commandDefinitions.itemById(CMD_ID)
            if cmd_def:
                cmd_def.deleteMe()

        _handlers.clear()
    except Exception:
        if _ui:
            _ui.messageBox('FGC Part Library failed to stop:\n{}'.format(traceback.format_exc()))
