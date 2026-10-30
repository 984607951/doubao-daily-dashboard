#!/bin/bash
# 每日报告一键入口（R1 唯一命令）：自动窗口采集分析 → 渲染 → 桌面/手机截图。
# 用法: bash run_daily.sh
set -e
cd "$(dirname "$0")"

echo "=== [1/2] 采集分析（build_report）==="
OUT=$(python3 build_report.py)
echo "$OUT"
DATE=$(echo "$OUT" | python3 -c "import sys,json;print(json.load(sys.stdin)['date'])")

echo "=== [2/2] 渲染截图（render_report: $DATE）==="
python3 render_report.py "$DATE"
