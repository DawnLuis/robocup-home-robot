#!/bin/bash
# 在 2026 官方平台上跑分（手动流程；避开 run_suite.sh 里写死的 2025 平台路径）
# 用法: bash run_on_2026.sh <题目目录> <标签>
E=/home/dawnluis/Downloads/env-release-2026
TD="${1:-/home/dawnluis/Downloads/robocup-home-robot/tests/stage1}"
TAG="${2:-p2026}"
cd "$E/bin" || { echo "找不到 2026 平台 bin/"; exit 1; }
pkill -x cserver 2>/dev/null
sleep 1
rm -rf log; mkdir -p log
./cserver -td "$TD" -eval ../lib/libasp -log log -mode nt -test all > /tmp/cs_${TAG}.out 2>&1 &
CS=$!
ok=0
for i in $(seq 1 15); do
  if ss -tln | grep -q 7932; then ok=1; break; fi
  sleep 1
done
[ $ok -eq 0 ] && { echo "server 未启动"; kill $CS 2>/dev/null; exit 1; }
timeout 400 ./example > /tmp/ex_${TAG}.out 2>&1
awk '/^<[0-9].*\.xml>/{t=$0;gsub(/[<>]/,"",t)} /^# Score:/{sum+=$3;n++;print t,$3} END{printf "总分 %d / %d 题\n",sum,n}' log/Dawnluis.log
cp log/Dawnluis.log /tmp/${TAG}.log 2>/dev/null
kill $CS 2>/dev/null
pkill -x cserver 2>/dev/null