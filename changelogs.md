# Changelog

## 1.0.0 - Initial Palworld Companion Tools Release

- Repositioned the project as a read-only Palworld companion application.
- Reduced navigation to Map, Breeding, Wiki, Settings, and About.
- Added an immutable `ReadOnlyWorldData` boundary with file fingerprint checks.
- Retained local World/Tree map inspection, markers, filters, overlays, and
  application-owned viewing annotations.
- Added an optional embedded MapGenie Palpagos Islands view.
- Isolated the breeding calculator from all save managers and added parent
  search, special combinations, starting/target paths, required Pals, and an
  unowned-partner option.
- Isolated the built-in Wiki from Pal editor code.
- Removed save editing, server administration, conversion, transfer, cleanup,
  inventory, character, Pal, guild, and base modification features.
- Removed writable CLI entry points and replaced the legacy updater with a
  release-only notification service.
- Added a per-user Windows setup package with Start Menu integration, optional
  desktop shortcut, and clean uninstall support.
- Added a Python-free portable ZIP built from the same standalone application.
- Added SHA-256 checksum generation for published Windows artifacts.
- Added optional daily checks for the latest stable GitHub Release.
- Added manual update checks in Settings and About plus a persistent available
  update indicator.
- Added strict release URL validation and semantic version comparison.
- Added tag/version enforcement to prevent mismatched release packages.
- Replaced editor-focused tests and packaging with companion-specific checks.
- Preserved the original MIT license and upstream attribution.
