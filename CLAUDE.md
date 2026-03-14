# CLAUDE.md

See [AGENTS.md](AGENTS.md) for the full project reference — architecture, commands, rules, and gotchas.

## Critical Rules

- **All 3 test suites must pass, zero skips, before any task is done:**
  ```bash
  uv run python -m pytest tests/unit/ tests/contract/ tests/test_e2e.py tests/test_tts_formats.py -q
  ```
- **Skips = failure.** Find the cause and fix it or tell the user.
- **Use `uv`, not `pip`.**
- **No commits without explicit user approval.**
