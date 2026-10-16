#!/bin/bash
# ============================================================
# RoboCup 仿真赛项 · 提交前终检(唯一标准=2026出题指南)
# 用法:  bash robocup-终检.sh <stage1目录> [stage2目录]
# 例  :  bash robocup-终检.sh ~/Downloads/stage1-submit-2026 ~/Downloads/stage2-submit-2026
# ============================================================
S="$HOME/.hermes/skills/software-development/robocup-home-robot/scripts"
IFS=$'\n'
for d in "$@"; do
  [ -d "$d" ] || { echo "跳过(非目录): $d"; continue; }
  name=$(basename "$d")
  echo ""
  echo "══════════ $name ══════════"
  echo -n "[1] 附录B 指令格式逐条比对      : "; python3 "$S/check_appendixB_2026.py" "$d" 2>/dev/null | tail -1
  echo -n "[2] 语法/格式(XML/括号/字段序)  : "; python3 "$S/check_syntax_2026.py" "$d" 2>/dev/null | tail -1
  echo -n "[3] 指南格式 rules(编号/颜色/满分): "; python3 "$S/check_rules_2026.py" "$d" 2>/dev/null | grep -E "有错误的题" | tr -d '\n'; python3 "$S/check_rules_2026.py" "$d" 2>/dev/null | grep -E "最低理论" | sed 's/^/  /'
  echo -n "[4] 约束初始态(破坏=真缺陷)     : "; python3 "$S/check_cons_init.py" "$d" 2>/dev/null | grep "有问题" | tail -1
  if echo "$name" | grep -qi stage2; then
    echo -n "[5] mis/err/extra 三段规则      : "; python3 "$S/check_stage2_2026.py" "$d" 2>/dev/null | tail -1
  fi
  echo -n "[6] 题目唯一性(md5)             : "; n=$(ls "$d"/*.xml 2>/dev/null | wc -l); u=$(md5sum "$d"/*.xml 2>/dev/null | awk '{print $1}' | sort -u | wc -l); echo "$n 题 / 唯一 $u"
  echo -n "[7] mis/err/ans 开关            : "; grep -ho 'mis="[a-z]*" err="[a-z]*" ans="[a-z]*"' "$d"/*.xml 2>/dev/null | sort -u | tr '\n' ' '; echo ""
  echo -n "[8] 容器描述字段序(附录A)       : "
  bad=$(grep -h "container)" "$d"/*.xml 2>/dev/null | grep -cE '\(sort [0-9]+ [a-z]+\) \(size [0-9]+ big\) \((type [0-9]+ container)\)')
  echo "顺序异常的容器行: $bad (应为0)"
done
echo ""
echo "★ 若想再跑官方 validator(语法+可解性):"
echo "   TO_MS=30000 bash $S/run_validate.sh <题目目录> <标签>   然后看 /tmp/val2026_<标签>/validator.out 的 valid/unvalid"