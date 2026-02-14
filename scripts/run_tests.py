#!/usr/bin/env python
"""
Vocal E2E Test Runner

Runs end-to-end integration tests for the Vocal API.
"""

import sys
import subprocess
from pathlib import Path


def main():
    """Run E2E tests"""
    test_file = Path(__file__).parent.parent / "tests" / "test_e2e.py"

    if not test_file.exists():
        print(f"Error: Test file not found: {test_file}")
        return 1

    assets_dir = Path("test_assets/audio")
    if not assets_dir.exists():
        print("Test assets not found. Generating...")
        result = subprocess.run(
            [sys.executable, "generate_test_assets.py"], capture_output=False
        )
        if result.returncode != 0:
            print("Failed to generate test assets")
            return 1

    print("\n" + "=" * 70)
    print("  VOCAL E2E INTEGRATION TESTS")
    print("=" * 70)
    print("\nStarting tests...\n")

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(test_file),
        "-v",
        "--tb=short",
        "-s",
        "--color=yes",
    ]

    result = subprocess.run(cmd)

    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
