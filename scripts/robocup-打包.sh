#!/bin/bash
# ============================================================
# RoboCup 仿真赛项 · 提交包生成
# 结构与命名严格对齐"上次实际提交并接受的包"(18-重庆科技大学-从容应对.zip):
#   <抽签顺序>-<学校>-<队伍名称>.zip            ← 外层
#     └─ <抽签顺序>-<学校>-<队伍名称>/
#          ├─ example.zip   内含 example/ + 参赛代码(源码)
#          └─ tests.zip     内含 tests/   + <抽签顺序>-<两位序号>.xml (如 7-01.xml ~ 7-30.xml)
# 用法: bash robocup-打包.sh <抽签顺序> <学校> <队伍名称> <stage1|stage2> [代码目录]
# 例  : bash robocup-打包.sh 7 重庆科技大学 Dawnluis stage1
# ============================================================
set -e
ORDER="${1:?需要 抽签顺序}"; SCHOOL="${2:?需要 学校}"; TEAM="${3:?需要 队伍名称}"
STAGE="${4:-stage1}"
CODE="${5:-$HOME/Downloads/robocup-home-robot/example}"
SRC="$HOME/Downloads/robocup-home-robot/tests/$STAGE"
OUT="$HOME/Downloads/提交包"
BASE="${ORDER}-${SCHOOL}-${TEAM}"                  # ★ 主文件夹名, 严格不加后缀
STAGE_NO="${STAGE#stage}"                         # stage1 -> 1
ZIP="$OUT/${BASE}_阶段${STAGE_NO}.zip"

[ -d "$SRC" ] || { echo "找不到题目目录: $SRC"; exit 1; }
[ -d "$CODE" ] || { echo "找不到代码目录: $CODE"; exit 1; }

rm -rf "$OUT/_work"; mkdir -p "$OUT/_work/tests" "$OUT/_work/example"

# ① 题目: 命名为 "<抽签顺序>-<两位序号>.xml"
i=1
for f in $(ls "$SRC"/*.xml | sort); do
  cp "$f" "$OUT/_work/tests/$(printf '%s-%02d.xml' "$ORDER" "$i")"
  i=$((i+1))
done
# ② 参赛代码(只要源码, 去掉构建产物)
cp -r "$CODE"/. "$OUT/_work/example/"
rm -rf "$OUT/_work/example/build" 2>/dev/null || true
find "$OUT/_work/example" -name '*.o' -delete 2>/dev/null || true

# ③ 三层层打包
mkdir -p "$OUT"
python3 - "$OUT/_work" "$BASE" "$ZIP" "$STAGE_NO" <<'PY'
import sys, os, zipfile
work, base, zpath, stage_no = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
d_tests  = os.path.join(work, 'tests')
d_example = os.path.join(work, 'example')

def zipdir(srcdir, arcroot, zpath):
    n = 0
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
        z.write(srcdir, arcroot)                       # 保留顶层目录项
        for dp, _, fs in os.walk(srcdir):
            for fn in sorted(fs):
                p = os.path.join(dp, fn)
                z.write(p, os.path.join(arcroot, os.path.relpath(p, srcdir)))
                n += 1
    return n

n1 = zipdir(d_tests,   'tests',   os.path.join(work, 'tests.zip'))
n2 = zipdir(d_example, 'example', os.path.join(work, 'example.zip'))

with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
    z.write(os.path.join(work, 'example.zip'), os.path.join(base, 'example.zip'))
    z.write(os.path.join(work, 'tests.zip'),   os.path.join(base, 'tests.zip'))

print('已生成: %s' % os.path.basename(zpath))
print('  %s/example.zip   (%d 个源码文件)' % (base, n2))
print('  %s/tests.zip     (%d 道题)' % (base, n1))
PY
echo ""
echo "=== 题目命名(前6 + 后2) ==="
ls "$OUT/_work/tests" | head -6 | sed 's/^/  /'
echo "  ..."
ls "$OUT/_work/tests" | tail -2 | sed 's/^/  /'
echo "输出: $ZIP"