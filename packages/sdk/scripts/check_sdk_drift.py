import filecmp
import sys
import tempfile
from pathlib import Path

from generate import VOCAL_SDK_DIR, run_generator


def _compare_dirs(left: Path, right: Path) -> list[str]:
    differences: list[str] = []
    comparison = filecmp.dircmp(left, right, ignore=["__pycache__"])

    for name in comparison.left_only:
        differences.append(f"Only in current SDK: {name}")
    for name in comparison.right_only:
        differences.append(f"Only in regenerated SDK: {name}")
    for name in comparison.diff_files:
        differences.append(f"Changed file: {name}")

    for subdir in comparison.common_dirs:
        differences.extend(_compare_dirs(left / subdir, right / subdir))

    return differences


def main() -> None:
    spec_path = Path(__file__).parent.parent / "openapi.json"
    if not spec_path.exists():
        print(f"Missing checked-in spec: {spec_path}")
        sys.exit(1)

    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp) / "vocal_sdk"
        run_generator("--path", str(spec_path), out_dir)
        differences = _compare_dirs(VOCAL_SDK_DIR, out_dir)

    if differences:
        print("SDK drift detected. Run: uv run python packages/sdk/scripts/generate.py --path packages/sdk/openapi.json")
        for diff in differences:
            print(diff)
        sys.exit(1)

    print("Generated SDK matches the checked-in OpenAPI spec.")


if __name__ == "__main__":
    main()
