# Contributing

Thank you for helping improve Palworld Companion Tools.

## Project Scope

Changes should support one or more of these areas:

- read-only map inspection;
- breeding calculation and path planning;
- bundled Wiki and game-data browsing;
- themes, localization, accessibility, packaging, or tests;
- stronger read-only safety guarantees.

Save editing, injection, cleanup, conversion, character transfer, player/Pal
modification, inventory management, and server administration are intentionally
outside this project's scope.

## Development Setup

```powershell
git clone https://github.com/rckieee-gif/Palworld-Companion-Tool.git
cd Palworld-Companion-Tool
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install .\src\palsav\palooz
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Run the application:

```powershell
.\.venv\Scripts\python.exe start.py
```

Run tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\validate_game_data.py
```

When bundled game data changes, regenerate and review its deterministic manifest:

```powershell
.\.venv\Scripts\python.exe scripts\generate_game_data_manifest.py
.\.venv\Scripts\python.exe scripts\validate_game_data.py
```

Build the Python-free Windows distribution and installer:

```powershell
.\.venv\Scripts\python.exe build\nuitka\build_nuitka.py --standalone
.\.venv\Scripts\python.exe build\verify_build.py
.\.venv\Scripts\python.exe build\installer\build_installer.py
.\.venv\Scripts\python.exe build\package_release.py
```

The installer step requires Inno Setup 6. `PRODUCT_VERSION` in `src/app_info.py`
and `project.version` in `pyproject.toml` must match. A release tag must be the
same version prefixed with `v`, for example `v1.0.0`.

## Pull Requests

1. Create a focused branch.
2. Keep changes inside the companion-only product boundary.
3. Add or update tests for behavior changes.
4. Run the full test suite.
5. Run game-data validation when resources or data loaders change.
6. Explain user impact and read-only implications in the pull request.
7. Do not include game saves, logs, credentials, build output, or user data.

Changes that touch world loading or map inspection must prove that input bytes,
size, hash, and modification time remain unchanged.

## Licensing

By contributing, you agree that your contribution may be distributed under the
repository's MIT license. Third-party code and assets must retain their own
required notices and compatible licenses.
