#!/usr/bin/env python3
# 诊断工具: 分析每题的 plate 物体 + 任务类型 + 小物体类型计数
# 用途: 定位"盘上物体被PickUp误拿"类低分题。若某类型物体只有1个且在盘上,
# 任何需要该类型的任务(pickup/putin/puton)都可能误选盘上物破坏plate约束。
# 用法: python3 plate_diag.py [题号...]   缺省分析一批典型题
import re, sys
P="/home/dawnluis/Downloads/Planner-release-2025/Planner-release-ubuntu18/tests/example"

def analyze(t):
    with open(f"{P}/{t}.xml") as f: s=f.read()
    info=re.search(r'<info>(.*?)</info>', s, re.S).group(1)
    instr=re.search(r'<instr>(.*?)</instr>', s, re.S).group(1)
    types={int(o):ty for o,ty in re.findall(r'\(sort (\d+) (\w+)\)', info)}
    plate=[int(p) for p in re.findall(r'\(plate (\d+)\)', info)]
    tasks=re.findall(r'\(:task \((\w+)(?: X)?\)', instr)
    cn=re.findall(r'cons_notnot\s*\(:info \(plate X\)[^)]*\)\(:cond[^)]*\(sort X (\w+)\)\)', instr)
    from collections import Counter
    cnt=Counter(types.values())
    print(f"{t}: plate={[(p,types.get(p)) for p in plate]} tasks={tasks} cons_notnot_plate={cn}")
    print(f"   类型计数={dict(cnt)}")
    return plate, types, tasks

if __name__=="__main__":
    args=sys.argv[1:] if len(sys.argv)>1 else [54,61,74,80,95,99,56,70,64,94]
    for t in args: analyze(t)
