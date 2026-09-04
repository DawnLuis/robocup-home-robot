#!/bin/bash
# 用法: run_suite.sh <testdir相对bin的路径> <版本标签> <轮数>
# 每轮: 起cserver → 跑example → 存log → 杀server → 打印总分
set -u
PLAT=/home/dawnluis/Downloads/Planner-release-2025/Planner-release-ubuntu18
TD="$1"; TAG="$2"; ROUNDS="$3"
cd "$PLAT/bin" || exit 1
for r in $(seq 1 "$ROUNDS"); do
  pkill -x cserver 2>/dev/null
  sleep 1
  rm -rf log; mkdir -p log
  ./cserver -td "$TD" -eval ../lib/libasp -log log -mode nt -test all > /tmp/cs_${TAG}_$r.out 2>&1 &
  CSPID=$!
  ok=0
  for i in $(seq 1 15); do
    if ss -tln | grep -q 7932; then ok=1; break; fi
    sleep 1
  done
  [ $ok -eq 0 ] && { echo "$TAG r$r: server failed to start"; kill $CSPID 2>/dev/null; continue; }
  timeout 400 ./example > /tmp/ex_${TAG}_$r.out 2>&1
  awk '/^<[0-9].*\.xml>/{t=$0; gsub(/[<>]/,"",t)} /^# Score:/{sum+=$3; n++} END{printf "%s r%d: %d (%d题)\n", TAGv, R, sum, n}' TAGv="$TAG" R="$r" log/Dawnluis.log
  cp log/Dawnluis.log "/tmp/${TAG}_r${r}.log"
  kill $CSPID 2>/dev/null
  wait $CSPID 2>/dev/null
done
echo ALLDONE
