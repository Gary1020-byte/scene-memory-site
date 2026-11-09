#!/usr/bin/env bash
# refresh.sh —— 重建庫並重啟後端
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
echo "▸ 重建庫…"
python3 backend/build_db.py --json
echo "▸ 重啟服務…"
if systemctl --user is-active --quiet scene-memory-backend 2>/dev/null; then
  systemctl --user restart scene-memory-backend
  echo "✓ 已重啟 systemd 服務"
else
  echo "! systemd 服務未啟用；請手動 node backend/server.mjs"
fi
echo "▸ 檢查…"
curl -fsS http://127.0.0.1:8787/api/meta | python3 -c "import json,sys; d=json.load(sys.stdin); print('✓', d['counts'])"
