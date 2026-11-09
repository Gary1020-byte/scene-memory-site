#!/usr/bin/env bash
# refresh_public.sh —— 重建公開版資料庫並重啟公開服務
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
echo "▸ 重建公開庫 + 下載包…"
python3 backend/build_public.py
echo "▸ 重啟服務…"
systemctl --user restart scene-memory-backend-public
sleep 1
echo "▸ 檢查…"
curl -fsS http://127.0.0.1:8788/api/meta | python3 -c "import json,sys; d=json.load(sys.stdin); print('✓', d['counts'])"
