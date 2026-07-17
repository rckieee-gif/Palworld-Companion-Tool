# Test suite

Run the companion test suite from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -c tests\pytest.ini tests
```

The suite covers the five-page application shell, feature-removal boundary,
read-only world loading, map interactions, breeding data and paths, Wiki search,
resources, localization, and the retained low-level parser primitives.
