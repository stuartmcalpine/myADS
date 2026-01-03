# myADS Test Suite

Minimal test suite for myADS using pytest.

## Running Tests

### Install with dev dependencies

```bash
pip install -e ".[dev]"
```

### Run all tests

```bash
pytest tests/
```

### Run with verbose output

```bash
pytest tests/ -v
```

### Run specific test file

```bash
pytest tests/test_database.py -v
```

### Run specific test

```bash
pytest tests/test_database.py::test_add_author -v
```

## Test Coverage

- **test_constants.py** - Database path resolution logic (env vars, XDG, legacy)
- **test_database.py** - Database operations, models, and relationships
- **test_cli.py** - CLI functionality and tracker operations
- **test_search.py** - Search query building and ORCID logic

## CI Integration

Tests run automatically on GitHub Actions for Python 3.8-3.12 on Ubuntu.
