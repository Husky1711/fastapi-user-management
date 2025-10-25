# Tests Package

This package contains all test files organized by type:

## Structure:
- `unit/` - Unit tests for individual components
- `integration/` - Integration tests for service interactions
- `e2e/` - End-to-end tests for complete workflows
- `fixtures/` - Test data and fixtures
- `utils/` - Test utilities and helpers

## Running Tests:
```bash
# Run all tests
pytest

# Run specific test types
pytest tests/unit/
pytest tests/integration/
pytest tests/e2e/

# Run with coverage
pytest --cov=.
```
