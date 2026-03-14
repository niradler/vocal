import json
import sys
from pathlib import Path

from vocal_api.main import app


def main() -> None:
    spec_path = Path(__file__).parent.parent / "openapi.json"
    if not spec_path.exists():
        print(f"Missing checked-in spec: {spec_path}")
        sys.exit(1)

    checked_in = json.loads(spec_path.read_text(encoding="utf-8"))
    generated = app.openapi()
    if checked_in != generated:
        print("OpenAPI drift detected. Run: uv run python packages/sdk/scripts/export_openapi.py")
        sys.exit(1)

    print("OpenAPI spec matches the current FastAPI app.")


if __name__ == "__main__":
    main()
