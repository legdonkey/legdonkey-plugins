#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
skill_dir="$(cd "$script_dir/.." && pwd)"

out_root="${CONTEXT_DOCTOR_OUTDIR:-${TMPDIR:-/tmp}/context-doctor}"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
out_dir="$out_root/$stamp"

usage="usage: $0 [-h|--help] [--session-snapshot /path/to/session-snapshot.json] [--platform claude|codex|both] [--github-stars cached|live|off]"

extra=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      echo "$usage"
      exit 0
      ;;
    --session-snapshot)
      if [[ -z "${2:-}" ]]; then
        echo "missing path after --session-snapshot" >&2
        exit 2
      fi
      extra+=(--session-snapshot "$2")
      shift 2
      ;;
    --platform)
      if [[ -z "${2:-}" ]]; then
        echo "missing value after --platform" >&2
        exit 2
      fi
      case "$2" in
        claude|codex|both) ;;
        *)
          echo "invalid value after --platform: $2 (expected claude|codex|both)" >&2
          exit 2
          ;;
      esac
      extra+=(--platform "$2")
      shift 2
      ;;
    --github-stars)
      if [[ -z "${2:-}" ]]; then
        echo "missing value after --github-stars" >&2
        exit 2
      fi
      case "$2" in
        cached|live|off) ;;
        *)
          echo "invalid value after --github-stars: $2 (expected cached|live|off)" >&2
          exit 2
          ;;
      esac
      extra+=(--github-stars "$2")
      shift 2
      ;;
    *)
      echo "$usage" >&2
      exit 2
      ;;
  esac
done

mkdir -p "$out_dir"

args=(
  --markdown "$out_dir/report.md"
  --json "$out_dir/inventory.json"
  --html "$out_dir/report.html"
)

python3 -B "$skill_dir/scripts/context_doctor.py" "${args[@]}" ${extra[@]+"${extra[@]}"}

python3 -B - "$out_dir/inventory.json" "$out_dir/report.md" "$out_dir/report.html" <<'PY'
import json
import sys
from pathlib import Path

inventory_path = Path(sys.argv[1])
report_path = Path(sys.argv[2])
html_path = Path(sys.argv[3])
data = json.loads(inventory_path.read_text(encoding="utf-8"))

print(f"HTML={html_path}")
print(f"报告={report_path}")
print(f"JSON={inventory_path}")
for platform in data.get("platforms", {}).values():
    if not platform.get("cli_present") and not platform.get("skills"):
        continue
    cli = "" if platform.get("cli_present") else "(CLI 未检测到)"
    print(
        f"{platform['label']}{cli}="
        f"已装:{len(platform.get('plugins', []))} "
        f"可装:{len(platform.get('available_plugins', []))} "
        f"市场:{len(platform.get('marketplaces', []))} "
        f"MCP:{len(platform.get('mcp_servers', []))} "
        f"独立技能:{len(platform.get('skills', []))}"
    )
print(f"建议数量={len(data.get('recommendations', []))}")
pending = data.get("pending_translation_count", 0)
print(f"待译中文={pending}（>0 时需在技能流程里翻译后用 --render-only 二次渲染）")
print(f"翻译缓存={data.get('translation_cache_path', '')}")
print(f"会话快照={'是' if data.get('session', {}).get('snapshot_provided') else '否'}")
PY
