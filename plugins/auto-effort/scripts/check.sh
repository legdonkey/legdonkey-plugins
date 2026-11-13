#!/usr/bin/env bash
# 本地检查：类型检查、mod 校验、mod 单元测试。不调用模型，不产生费用。
set -euo pipefail
cd "$(dirname "$0")/.."
TSC=$(command -v tsc || true)
[ -n "$TSC" ] || TSC="npx --yes --registry=https://registry.npmmirror.com -p typescript@5.9.3 tsc"
$TSC -p tsconfig.json
claude plugin validate .
if compgen -G "tests/*.test.ts" > /dev/null || compgen -G "tests/*.test.tsx" > /dev/null; then
  # 生成的接口文档包含其他插件的测试，只在副本中排除文档与 Git 元数据。
  check_dir=$(mktemp -d)
  trap 'rm -rf "$check_dir"' EXIT
  tar --exclude='./dev' --exclude='./.git' --exclude='./.claude-plugin/types' -cf - . | tar -xf - -C "$check_dir"
  (cd "$check_dir" && claude plugin test .)
fi
echo "check: 全部通过"
