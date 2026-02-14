# End-to-End Integration Tests

Comprehensive E2E integration tests for the Vocal API.

## Running Tests

```bash
# Full test suite
uv run python scripts/run_tests.py

# Or use pytest directly  
uv run pytest tests/test_e2e.py -v
```

## Test Coverage

**24 E2E Integration Tests:**
- API Health (2 tests)
- Model Management (5 tests)
- Audio Transcription/STT (7 tests)
- Text-to-Speech/TTS (5 tests)
- Error Handling (4 tests)
- Performance (1 test)

## Test Assets

Generate real speech test files:
```bash
uv run python scripts/create_test_assets.py
```

This creates audio files with real speech for validation.
