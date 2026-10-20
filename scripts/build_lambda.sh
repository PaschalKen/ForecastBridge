#!/usr/bin/env bash
# Build the zips uploaded to the two Lambda functions:
#   build/collector.zip -> forecastbridge-collector (hourly job)
#   build/api.zip       -> forecastbridge-api       (FastAPI app + web page)
# Usage: ./scripts/build_lambda.sh
set -euo pipefail

cd "$(dirname "$0")/.."  # run from the project root, wherever the script is called from

rm -rf build
mkdir -p build

# build_zip NAME INCLUDE_STATIC PACKAGE...
#   Installs PACKAGE... at the versions pinned in requirements.txt, adds our app/ code
#   (with or without the web page), and zips it all as build/NAME.zip.
build_zip() {
  local name=$1 include_static=$2
  shift 2
  local package_dir="build/$name"
  mkdir -p "$package_dir"

  # 1. Libraries, at the versions in requirements.txt. boto3 is left out because Lambda's
  #    Python runtime already includes it. --platform/--python-version fetch Linux ARM builds
  #    to match the Lambda (arm64, Python 3.12), not macOS ones.
  local pattern
  pattern="^($(IFS='|'; echo "$*"))=="
  grep -E "$pattern" requirements.txt | sed 's/ *#.*//' > "build/$name-requirements.txt"
  python3 -m pip install --quiet \
    --requirement "build/$name-requirements.txt" \
    --target "$package_dir" \
    --platform manylinux2014_aarch64 \
    --python-version 3.12 \
    --implementation cp \
    --only-binary=:all:

  # 2. Our own code, without cached bytecode (and without the web page unless asked)
  cp -R app "$package_dir/app"
  if [ "$include_static" != "yes" ]; then
    rm -rf "$package_dir/app/static"
  fi
  find "$package_dir" -name "__pycache__" -type d -prune -exec rm -rf {} +

  # 3. Zip it so app/ and the libraries sit at the top level of the zip, where Lambda looks
  (cd "$package_dir" && zip -qr "../$name.zip" .)
  echo "Built build/$name.zip ($(du -h "build/$name.zip" | cut -f1))"
}

build_zip collector no requests python-dotenv
build_zip api yes requests python-dotenv fastapi mangum
