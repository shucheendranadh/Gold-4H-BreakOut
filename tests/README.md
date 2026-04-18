# Test Suite Structure

This directory contains all tests for the GOLD trading system.

## Directory Structure

```
tests/
├── __init__.py                    # Root test package
├── premarket/                     # Premarket analysis tests
│   ├── __init__.py
│   ├── conftest.py               # Pytest fixtures for premarket tests
│   ├── test_position_manager.py  # Unit tests for PositionManager
│   ├── test_premarket_integration.py  # Integration tests for premarket workflow
│   └── test_utils.py             # Test utility functions
└── README.md                      # This file
```

## Running Tests

### Run all tests:
```powershell
python -m pytest tests/ -v
```

### Run premarket tests only:
```powershell
python -m pytest tests/premarket/ -v
```

### Run specific test file:
```powershell
python -m pytest tests/premarket/test_position_manager.py -v
```

### Run with coverage:
```powershell
python -m pytest tests/ --cov=Core --cov=premarket --cov-report=html
```

## Test Categories

### Premarket Tests (27 tests)

- **Unit Tests (18 tests)**: Test individual methods in `PositionManager`
  - `cleanup_stale_state` - 7 tests
  - `_check_for_external_triggers` - 6 tests
  - `handle_daily_maintenance` - 5 tests

- **Integration Tests (9 tests)**: Test full premarket workflow
  - Workflow tests - 4 tests
  - File operations - 3 tests
  - Edge cases - 2 tests

## Adding New Tests

When adding tests for new features:

1. Create a new subdirectory under `tests/` for the feature (e.g., `tests/market/`)
2. Add `__init__.py` and `conftest.py` with relevant fixtures
3. Create test files with descriptive names (e.g., `test_order_execution.py`)
4. Follow the existing naming conventions and structure

## Test Fixtures

Common fixtures are defined in `conftest.py` files:

- `mock_order_manager` - Mock for OrderManager
- `mock_state_manager` - Mock for StateManager
- `mock_historical_fetcher` - Mock for HistoricalDataFetcher
- Various state fixtures (empty, clean, stale, triggered)
- GTT response fixtures for different scenarios

## Best Practices

- Keep tests focused and independent
- Use descriptive test names that explain what is being tested
- Mock external dependencies (API calls, file I/O)
- Test both success and failure scenarios
- Validate bug fixes with dedicated tests
