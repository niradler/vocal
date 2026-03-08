import json
from pathlib import Path

from vocal_api.main import app


def main() -> None:
    output_path = Path(__file__).parent.parent / "openapi.json"
    spec = app.openapi()
    output_path.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote OpenAPI spec to {output_path}")


if __name__ == "__main__":
    main()
