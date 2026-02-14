"""
Generate Python SDK from OpenAPI spec
"""
import subprocess
import sys
from pathlib import Path


def generate_sdk():
    """Generate SDK from OpenAPI spec"""
    sdk_dir = Path(__file__).parent.parent
    openapi_file = sdk_dir / "openapi.json"
    output_dir = sdk_dir / "vocal_sdk"
    
    if not openapi_file.exists():
        print(f"Error: {openapi_file} not found")
        print("Download it first:")
        print("  curl http://localhost:8000/openapi.json -o packages/sdk/openapi.json")
        sys.exit(1)
    
    print("Generating SDK from OpenAPI spec...")
    
    # Generate Pydantic models
    subprocess.run([
        "datamodel-codegen",
        "--input", str(openapi_file),
        "--input-file-type", "openapi",
        "--output", str(output_dir / "models.py"),
        "--field-constraints",
        "--use-standard-collections",
    ], check=True)
    
    print(f"✓ Generated models at {output_dir / 'models.py'}")
    print("\nSDK generated successfully!")
    print(f"Location: {output_dir}")


if __name__ == "__main__":
    generate_sdk()
