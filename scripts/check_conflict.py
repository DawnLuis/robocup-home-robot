#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""结构性冲突检查: cons 的目标物体是否被 task 引用(共用物体极易导致 task/cons 互斥 => validator UNSAT)"""
import re, glob, sys
sys.path.insert(0, '/tmp')
from check_cons_init import parse_sexp, atoms, load_objects, resolve, State


def analyze(path):
    raw = open(path, encoding='utf-8', errors='replace').read()
    objs = load_objects(raw)
    v = State(raw, visible=True)
    mi = re.search(r'<instr>(.*?)</instr>', raw, re.S)
    root = None
    for e in parse_sexp(mi.group(1)):
        if isinstance(e, list) and e and str(e[0]).startswith(':ins'):
            root = e
    cmds = [c for c in root[1:] if isinstance(c, list) and c and str(c[0]).startswith(':')]

    def conds_of(x):
        out = []
        for y in x:
            if isinstance(y, list) and y and y[0] == ':cond':
                out = atoms(y[1:])
        return out

    tasks, cons = [], []
    for c in cmds:
        if c[0] == ':task':
            tasks.append((c[1][0], c[1][1:], conds_of(c)))
        elif c[0] in (':cons_not', ':cons_notnot'):
            inner = c[1]
            iconds = conds_of(inner)
            if inner[0] == ':task':
                cons.append((c[0], 'task', inner[1][0], inner[1][1:], iconds))
            else:
                cons.append((c[0], 'info', inner[1][0], inner[1][1:], iconds))
    out = []
    SMALLSET = set("book can remotecontrol bottle cup".split())
    for kind, tp, pred, args, cd in cons:
        # 只有 *info* 类约束(object/容器状态必须全程保持)被 task 搬动同一"小物体"才是真冲突;
        # cons_not(task ...) 与 task 共用物体是正常的("Do not X" 本就针对同一物体)
        if tp != 'info':
            continue
        r = resolve(cd, objs, v.colors)
        objsX = set(r.get('X', [])).union(set(r.get('Y', [])))
        objsX = set(o for o in objsX if objs.get(o) in SMALLSET)
        for tp2, pred2, cd2 in tasks:
            r2 = resolve(cd2, objs, v.colors)
            o2 = set(r2.get('X', [])).union(set(r2.get('Y', [])))
            same = objsX.intersection(o2)
            if same:
                out.append('%s%s(%s) 与 task(%s) 共用小物体 %s (需人工确认是否互斥)' % (kind, tp, pred, pred2, sorted(same)))
    return out


if __name__ == '__main__':
    for d in sys.argv[1:]:
        fs = sorted(glob.glob(d + '/*.xml'))
        n = 0
        print("### %s (%d题)" % (d, len(fs)))
        for f in fs:
            try:
                r = analyze(f)
            except Exception as e:
                print("  解析失败", f, e); continue
            if r:
                n += 1
                print("  ", f.split('/')[-1], r[:2])
        print("  -> 共用物体(潜在冲突)的题数:", n, "/", len(fs))