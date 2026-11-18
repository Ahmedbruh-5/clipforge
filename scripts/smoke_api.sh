#!/usr/bin/env bash
# Quick API smoke checks against a running backend (default localhost:8000).
set -euo pipefail

BASE_URL="${CLIPFORGE_API:-http://127.0.0.1:8000}"

echo "Health:"
curl -sf "$BASE_URL/api/health" | python3 -m json.tool

echo
echo "Dashboard:"
curl -sf "$BASE_URL/api/dashboard" | python3 -m json.tool

echo
echo "Videos:"
curl -sf "$BASE_URL/api/videos" | python3 -m json.tool

echo
echo "YouTube status:"
curl -sf "$BASE_URL/api/youtube/status" | python3 -m json.tool

echo
echo "Smoke OK"
