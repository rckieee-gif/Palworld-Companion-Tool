# Palworld Companion Tools Contributor Notes

## Product boundary

The desktop application has seven navigation entries only: Map, Breeding, Stats
Calculator, Team Builder, Wiki, Settings, and About. It is an informational
companion, not a save editor.

The application may decode `Level.sav` and sibling player saves for map markers.
It must never expose or call save serialization, overwrite, conversion, repair,
transfer, injection, cleanup, player editing, Pal editing, guild editing, base
editing, inventory editing, or server administration code.

## Retained architecture

- `src/palworld_aio/read_only_world.py`: immutable map-facing save boundary.
- `src/palworld_aio/ui/tabs/map_tab.py`: fully local World/Tree map explorer.
- `src/palworld_aio/map/locations.py`: bundled locations and local map-pin records.
- `src/palworld_aio/ui/tabs/breeding_tab.py`: standalone breeding tools.
- `src/palworld_aio/ui/tabs/stats_calculator_tab.py`: manual, read-only IV
  estimation UI.
- `src/palworld_aio/stat_calculator.py`: testable formula and validation layer.
- `src/palworld_aio/pal_stats_repository.py`: bundled Pal base-stat lookup.
- `src/palworld_aio/ui/tabs/team_builder_tab.py`: standalone party planning.
- `src/palworld_aio/team_builder.py`: team data contracts, filtering, analysis,
  URL parsing, and history.
- `src/palworld_aio/team_storage.py`: versioned, app-local saved teams.
- `src/palworld_aio/ui/tabs/docs/wiki_tab.py`: bundled Wiki.
- `src/palworld_aio/game_data.py`: read-only bundled data access.
- `src/palsav`: vendored low-level decoder dependency. Its serializer internals
  are not application APIs.

Preferences, map annotations, and saved team configurations may be written only
to the application config directory returned by
`resource_resolver.get_user_config_dir()`.

## Verification

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests
.\.venv\Scripts\python.exe build\nuitka\build_nuitka.py --standalone
.\.venv\Scripts\python.exe build\verify_build.py
```

Any map-loading change must preserve the tests that compare save bytes, size,
SHA-256 hash, and modification time before and after UI interaction.

The root MIT license and upstream attribution must remain present. The vendored
parser's separate license remains under `src/palsav/LICENSE`.
