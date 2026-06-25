#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
skill_dir="$(cd "$script_dir/.." && pwd)"

out_root="${CODEX_CONTEXT_DOCTOR_OUTDIR:-${TMPDIR:-/tmp}/codex-context-doctor}"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
out_dir="$out_root/$stamp"
mkdir -p "$out_dir"

args=(
  --markdown "$out_dir/report.md"
  --json "$out_dir/inventory.json"
)

if [[ "${1:-}" == "--session-snapshot" ]]; then
  if [[ -z "${2:-}" ]]; then
    echo "missing path after --session-snapshot" >&2
    exit 2
  fi
  args+=(--session-snapshot "$2")
elif [[ $# -gt 0 ]]; then
  echo "usage: $0 [--session-snapshot /path/to/session-snapshot.json]" >&2
  exit 2
fi

python3 -B "$skill_dir/scripts/codex_context_doctor.py" "${args[@]}"

python3 -B - "$out_dir/inventory.json" "$out_dir/report.md" <<'PY'
import json
import sys
from pathlib import Path

inventory_path = Path(sys.argv[1])
report_path = Path(sys.argv[2])
data = json.loads(inventory_path.read_text(encoding="utf-8"))
counts = data["counts"]
duplicates = data.get("duplicates", {}).get("plugins_by_name", {})
recommendations = data.get("recommendations", [])

print(f"报告={report_path}")
print(f"JSON={inventory_path}")
print(
    "统计="
    f"插件:{counts['plugins']} "
    f"App/连接器:{counts['apps']} "
    f"MCP:{counts['mcp_servers']} "
    f"技能:{counts['skills']} "
    f"市场源:{counts['marketplaces']}"
)
if duplicates:
    print("重名插件=" + ", ".join(f"{name}:{len(ids)}" for name, ids in duplicates.items()))
else:
    print("重名插件=无")
print(f"建议数量={len(recommendations)}")
print(f"会话快照={'是' if data.get('session', {}).get('snapshot_provided') else '否'}")
PY
