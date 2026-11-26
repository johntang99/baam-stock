#!/usr/bin/env bash
# Generates pydantic v2 models from schemas into services/py/sr/contracts/models.py
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
repo="$(cd "$here/../.." && pwd)"
cd "$repo"
uv run datamodel-codegen \
  --input "$here/schemas" --input-file-type jsonschema \
  --output "$repo/services/py/sr/contracts/_gen" \
  --output-model-type pydantic_v2.BaseModel \
  --target-python-version 3.12 \
  --use-standard-collections --use-union-operator \
  --field-constraints --use-double-quotes --disable-timestamp \
  --custom-file-header "# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit."
echo "pydantic models -> services/py/sr/contracts/_gen/"
