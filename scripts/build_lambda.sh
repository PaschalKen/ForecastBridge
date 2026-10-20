#!/usr/bin/env bash
# Build build/collector.zip: the zip uploaded to the forecastbridge-collector Lambda function.
# Usage: ./scripts/build_lambda.sh
set -euo pipefail

cd "$(dirname "$0")/.."  # run from the project root, wherever the script is called from

PACKAGE_DIR=build/package
ZIP_FILE=build/collector.zip

rm -rf build
mkdir -p "$PACKAGE_DIR"

# 1. Libraries the collector needs, at the versions pinned in requirements.txt.
#    boto3 is left out because Lambda's Python runtime already includes it.
#    --platform/--python-version fetch Linux ARM builds to match the Lambda (arm64, Python 3.12),
#    not macOS ones.
grep -E '^(requests|python-dotenv)==' requirements.txt > build/lambda-requirements.txt
python3 -m pip install --quiet \
  --requirement build/lambda-requirements.txt \
  --target "$PACKAGE_DIR" \
  --platform manylinux2014_aarch64 \
  --python-version 3.12 \
  --implementation cp \
  --only-binary=:all:

# 2. Our own code, without the web page or cached bytecode
cp -R app "$PACKAGE_DIR/app"
rm -rf "$PACKAGE_DIR/app/static"
find "$PACKAGE_DIR" -name "__pycache__" -type d -prune -exec rm -rf {} +

# 3. Zip it so app/ and the libraries sit at the top level of the zip, where Lambda looks
(cd "$PACKAGE_DIR" && zip -qr "../collector.zip" .)

echo "Built $ZIP_FILE ($(du -h "$ZIP_FILE" | cut -f1))"
