#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose run --rm -p 3334:3334 hsb npx -y mcp-remote https://mcp.linear.app/mcp
