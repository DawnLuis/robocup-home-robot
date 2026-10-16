#!/bin/bash
# 用官方validator校验题目(语法/格式/ASP可解性), 提前发现会被扣500分的错题
# usage: VALIDATOR=/path/to/validator bash run_validate.sh <abs_tests_dir> <label>
set -u
SRC=/home/dawnluis/Downloads/env-release-2026
TESTS="$1"; LABEL="${2:-run}"
VALIDATOR="${VALIDATOR:-$SRC/bin/validator}"
W=/tmp/val2026_$LABEL
rm -rf "$W"; mkdir -p "$W/log" "$W/_tmp"
cd "$W"
cp "$SRC/bin/cserver" ./cserver
cp "$VALIDATOR" ./validator
cp "$SRC/bin/vrunact.sh" "$SRC/bin/vruntask.sh" .
cp "$SRC/lib/libasp.so" .
cp "$SRC/res/evaluate.lp" "$SRC/res/forcons.lp" "$SRC/res/fortask.lp" "$SRC/res/show.lp" "$SRC/res/iclingo" .
cp "$SRC/tools/validate_tests/testDevil.lp" "$SRC/tools/validate_tests/testshow.lp" "$SRC/tools/validate_tests/testvruntask.sh" "$SRC/tools/validate_tests/testkill.sh" .
chmod +x cserver validator iclingo *.sh
cp "$TESTS"/*.xml _tmp/
( cd _tmp && ls *.xml > test.list )
pkill -x cserver 2>/dev/null; sleep 0.3
./cserver -td _tmp -eval ./libasp -log log -to ${TO_MS:-5000} > cserver.out 2>&1 &
CS=$!
sleep 1
LD_LIBRARY_PATH=/tmp/boostshim ./validator > validator.out 2>&1
kill $CS 2>/dev/null; pkill -x cserver 2>/dev/null; sleep 0.3
echo "########## WORKDIR: $W ##########"
echo "=== 逐题校验结论(valid/unvalid) ==="
grep -E "Test '.*' is (un)?valid" validator.out
echo "=== 汇总 ==="
echo -n "valid  : "; grep -c "is valid" validator.out
echo -n "unvalid: "; grep -c "is unvalid" validator.out
echo "=== 报错细节(testlog.txt 尾30行) ==="
tail -30 testlog.txt 2>/dev/null
echo "=== 崩溃/异常 ==="
grep -iE "assert|error|Assertion|killed|已中止" validator.out | head -10
echo "=== cserver 每题结果 ==="
grep -E "^# Testing|^# Score" cserver.out | paste - - | head -60