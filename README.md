# Palworld Companion Tools

Palworld Companion Tools is a focused desktop companion for Palworld. It keeps
three informational features from PalworldSaveTools and removes the save editor,
server administration, cleanup, transfer, conversion, inventory, character,
guild, base, and Pal modification tools.

The application provides:

- **Interactive Map Viewer** for the bundled World and Tree maps, read-only save
  markers, filters, coordinates, overlays, local annotations, and an optional
  embedded MapGenie view.
- **Breeding Calculator** for parent-to-child results, desired-child parent
  searches, special combinations, breeding paths, required Pals, and optional
  unowned breeding partners.
- **Built-in Wiki** for Pals, items, buildings, technologies, active and passive
  skills, elements, and work suitability using bundled game data.

Breeding and Wiki work immediately. Loading a save is optional and is used only
to place bases and players on the local map.

## Read-Only Guarantee

Palworld saves are immutable inputs to this application.

- The retained application imports only the decoder interface used to parse a
  selected `Level.sav` and, when available, matching files in `Players`.
- No application service or UI action serializes, overwrites, patches, restores,
  injects, converts, or replaces a `.sav` file.
- The loader fingerprints input files before and after parsing and rejects a load
  if the world changes while it is being read.
- Map annotations, theme, language, and the last-opened folder are stored in the
  Palworld Companion Tools configuration directory, never in a Palworld save.
- Automated tests verify save bytes, size, SHA-256 hash, and modification time
  remain unchanged after loading, map navigation, overlay toggles, marker
  inspection, and closing a world.

No backup is created during loading because the app never writes to the save.

## Install And Run

### Packaged Windows build

Run `PalworldCompanionTools-V2.1.0-win.exe` from the packaged release or build
directory. The current development and packaging validation is performed on
Windows 11.

### Run from source

Requirements:

- Python 3.11 or newer
- Git
- [uv](https://docs.astral.sh/uv/) or `pip`

From this source checkout with `uv`:

```powershell
uv sync --group dev
uv run python start.py
```

Or with a conventional virtual environment on Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe start.py
```

Linux and macOS can run the source build with the corresponding virtual
environment paths. Native packaged builds for those platforms must be produced
and verified on that operating system.

## Loading A World

Open **Map**, select **Load world**, and choose `Level.sav`. Dragging one
`Level.sav` onto the window performs the same read-only load.

Common locations include:

- Windows Steam:
  `%LOCALAPPDATA%\Pal\Saved\SaveGames\<SteamID>\<WorldID>\Level.sav`
- Windows dedicated server:
  `PalServer\Pal\Saved\SaveGames\0\<WorldID>\Level.sav`
- Linux Steam/Proton:
  `~/.local/share/Steam/steamapps/compatdata/1623730/pfx/drive_c/users/steamuser/AppData/Local/Pal/Saved/SaveGames/<SteamID>/<WorldID>/Level.sav`

The sibling `Players` folder is optional. When it is missing, the map still
shows world and base information but reports that player markers are unavailable.

## Privacy

Save parsing and bundled Wiki/Breeding searches happen locally on the device.
The application does not upload save data, player identifiers, or world data.
The optional interactive MapGenie page requires an internet connection and is a
third-party website; opening it is separate from loading a local save.

## Test

```powershell
.\.venv\Scripts\python.exe -m pytest tests
```

The suite covers startup without a save, the five allowed navigation entries,
feature-removal boundaries, read-only file invariants, map interactions,
breeding formulas and special combinations, required-Pal paths, Wiki categories
and search, localization, resources, and packaging configuration.

## Build

Create a standalone distribution with Nuitka:

```powershell
.\.venv\Scripts\python.exe build\nuitka\build_nuitka.py --standalone
.\.venv\Scripts\python.exe build\verify_build.py
```

Use `--onefile` instead of `--standalone` for a single executable. Build output
is written under `dist`, and `build/nuitka-report.xml` records bundled modules
and resources.

## Limitations

- Palworld save formats and game data change over time. A newer game version may
  require a parser or bundled-data update.
- Save inspection currently focuses on guild, base, and last-known player
  locations needed by the Map Viewer.
- The built-in Wiki reflects bundled data and is not an official live database.
- The embedded MapGenie view requires Qt WebEngine and network access. A browser
  fallback is provided when embedding is unavailable.
- Local annotations are viewing notes only and are never imported into the game.

## Attribution And License

This project is a streamlined derivative of PalworldSaveTools. It retains the
original MIT license and attribution. The save-editing and server-administration
features have been removed.

The root [`license`](license) preserves the original MIT copyright notice:
Copyright (c) 2026 Pylar. Upstream source and history are available at
[deafdudecomputers/PalworldSaveTools](https://github.com/deafdudecomputers/PalworldSaveTools).

The vendored `palsav-flex` / `palooz` parser dependency carries its own
GPL-3.0-or-later license in [`src/palsav/LICENSE`](src/palsav/LICENSE).

Palworld and related names, trademarks, and game assets belong to Pocketpair and
their respective owners. This project is not affiliated with, endorsed by, or
sponsored by Pocketpair. MapGenie is a third-party service and is not affiliated
with this project.
