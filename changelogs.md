# Changelog

## 2.1.0 - Palworld Companion Tools

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
- Removed updater and writable CLI entry points from the application package.
- Replaced editor-focused tests and packaging with companion-specific checks.
- Preserved the original MIT license and upstream attribution.
