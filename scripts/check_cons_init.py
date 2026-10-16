#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
约束初始满足性检查 (2026指南: "一开始的环境状态就破坏了约束, 约束不会发生作用")
约束语义(rules 2.5 + forcons.lp + testDevil.lp):
  cons_not(...)   -> 该条件在每一步(含初始)都必须为假 => 初始必须"不满足"
  cons_notnot(..) -> 该条件在每一步(含初始)都必须为真 => 初始必须"满足"
  cons_not(:task X) -> 该动作目标在每一步都不得达成 => 初始必须"未达成"
真值来源: 评分用真状态=info+mis+r (+extra); 机器人/validator看到的是 info+w(stage2)
用法: python3 check_cons_init.py <目录> [目录...]
"""
import re, sys, os, glob, collections

SMALL = set("book can remotecontrol bottle cup".split())
CONTAINERS = set("closet cupboard refrigerator microwave".split())
BIG = set("human plant couch chair sofa bed table workspace worktable teapoy desk television airconditioner washmachine".split())


def parse_sexp(s):
    toks = re.findall(r'\(|\)|[^\s()]+', s)
    st = [[]]
    for t in toks:
        if t == '(':
            st.append([])
        elif t == ')':
            if len(st) < 2:
                raise ValueError('多余右括号')
            top = st.pop(); st[-1].append(top)
        else:
            st[-1].append(t)
    if len(st) != 1:
        raise ValueError('缺 %d 个右括号' % (len(st) - 1))
    return st[0]


def atoms(x):
    return [(e[0], e[1:]) for e in x if isinstance(e, list) and e and isinstance(e[0], str)]


def sbody(tag, txt):
    m = re.search(r'<%s>(.*?)</%s>' % (tag, tag), txt, re.S)
    return m.group(1) if m else ''


class State:
    def __init__(self, raw, visible=False):
        self.at = {}          # id -> loc
        self.inside = {}      # id -> container
        self.opened = {}
        self.hold = []; self.plate = []
        self.types = {}       # id -> sort
        self.colors = {}
        self.robot_at = None
        text = ''
        env = re.search(r'<env([^>]*)>(.*?)</env>', raw, re.S)
        flags = dict(re.findall(r'(\w+)\s*=\s*"(\w+)"', env.group(1)))
        whole = env.group(2)
        parts = [sbody('info', whole)]
        if not (visible and flags.get('mis') == 'on'):
            parts.append(sbody('mis', whole))
        err = sbody('err', whole)
        if err:
            parts.append(sbody('w', err) if (visible and flags.get('err') == 'on') else sbody('r', err))
        self.parts = parts
        for p in parts:
            for pred, a in atoms(parse_sexp(p)):
                self.apply(pred, a)

    def apply(self, pred, a):
        if not a:
            return
        v = a[0]
        if pred == 'sort':
            self.types[v] = a[1] if len(a) > 1 else '?'
        elif pred == 'color':
            self.colors[v] = a[1] if len(a) > 1 else '?'
        elif pred == 'at':
            if v == '0':
                self.robot_at = a[1]
            else:
                self.at[v] = a[1]
        elif pred == 'inside':
            self.inside[v] = a[1]
        elif pred in ('opened', 'closed'):
            self.opened[v] = (pred == 'opened')
        elif pred == 'hold':
            if v != '0':
                self.hold.append(v)
        elif pred == 'plate':
            if v != '0':
                self.plate.append(v)

    def loc_of(self, i, depth=0):
        """物体所在位置(容器内则继承容器位置)"""
        if depth > 6:
            return None
        if i in self.inside:
            return self.loc_of(self.inside[i], depth + 1)
        if i in self.at:
            return self.at[i]
        if i in self.hold or i in self.plate:
            return self.robot_at
        return None

    def sameplace(self, a, b):
        la, lb = self.loc_of(a), self.loc_of(b)
        if la is None or lb is None:
            return None      # 未知
        return la == lb

    def ev_info(self, pred, args, var_map):
        """求 info 谓词的真值, None=未知"""
        a = [var_map.get(x, x) for x in args]
        if pred in ('on', 'near'):
            return self.sameplace(a[0], a[1])
        if pred == 'at':
            return self.at.get(a[0]) == a[1] if a[0] in self.at else None
        if pred == 'inside':
            return self.inside.get(a[0]) == a[1]
        if pred == 'opened':
            return self.opened.get(a[0])
        if pred == 'closed':
            return (not self.opened[a[0]]) if a[0] in self.opened else None
        if pred == 'plate':
            return a[0] in self.plate
        if pred == 'hold':
            return a[0] in self.hold
        return None


def load_objects(raw):
    env = re.search(r'<env([^>]*)>(.*?)</env>', raw, re.S)
    whole = env.group(2)
    txt = sbody('info', whole) + sbody('mis', whole)
    err = sbody('err', whole)
    txt += sbody('r', err) + sbody('w', err)
    objs = {}
    for pred, a in atoms(parse_sexp(txt)):
        if pred == 'sort' and len(a) >= 2:
            objs[a[0]] = a[1]
    return objs


def resolve(conds, objs, colors):
    """把 (sort X book)(color X red) 之类解成 X->objid"""
    out = {}
    byvar = collections.defaultdict(dict)
    for pred, a in conds:
        if len(a) >= 2 and a[0] in ('X', 'Y'):
            byvar[a[0]][pred] = a[1]
    for var, d in byvar.items():
        cands = []
        for i, s in objs.items():
            if 'sort' in d and s != d['sort']:
                continue
            if 'color' in d and colors.get(i) != d['color']:
                continue
            cands.append(i)
        out[var] = cands
    return out


def check(path):
    raw = open(path, encoding='utf-8', errors='replace').read()
    objs = load_objects(raw)
    visible = State(raw, visible=True)
    truth = State(raw, visible=False)
    mi = re.search(r'<instr>(.*?)</instr>', raw, re.S)
    issues = []
    if not mi:
        return ['缺 instr']
    root = None
    for e in parse_sexp(mi.group(1)):
        if isinstance(e, list) and e and str(e[0]).startswith(':ins'):
            root = e
    if root is None:
        return ['instr 括号不匹配']
    cmds = [c for c in root[1:] if isinstance(c, list) and c and isinstance(c[0], str) and c[0].startswith(':')]
    for c in cmds:
        if c[0] not in (':cons_not', ':cons_notnot'):
            continue
        inner = c[1] if len(c) > 1 and isinstance(c[1], list) else None
        if inner is None:
            issues.append('%s 无内层' % c[0]); continue
        conds = []
        for x in inner[1:]:
            if isinstance(x, list) and x and x[0] == ':cond':
                conds = atoms(x[1:])
        var = resolve(conds, objs, visible.colors)
        itype = inner[0]                     # ':info' 或 ':task'
        body = inner[1] if len(inner) > 1 and isinstance(inner[1], list) else []
        if itype == ':task':
            pred = body[0] if body else '?'
        else:
            pred = body[0] if body else '?'
            if body:
                body = body[1:]
        if itype == ':task':
            # cons_not(:task ...) 初始必须未达成
            t = pred
            vmap = {k: (v[0] if v else '?') for k, v in var.items()}
            if t == 'open':
                iv = visible.opened.get(vmap.get('X'))
                if c[0] == ':cons_not' and iv is True:
                    issues.append('初始已满足 cons_not(task open %s) -> 约束一开始就被破坏' % vmap.get('X'))
            elif t == 'close':
                iv = visible.opened.get(vmap.get('X'))
                if c[0] == ':cons_not' and iv is False:
                    issues.append('初始已满足 cons_not(task close %s)(已关) -> 约束一开始就被破坏' % vmap.get('X'))
            elif t in ('pickup', 'putdown'):
                x = vmap.get('X')
                inhand = x in visible.hold or x in visible.plate
                if c[0] == ':cons_not' and t == 'pickup' and inhand:
                    issues.append('初始已满足 cons_not(task pickup %s)(已持有/在盘) ' % x)
                if c[0] == ':cons_not' and t == 'putdown' and not inhand:
                    issues.append('初始已满足 cons_not(task putdown %s)(已在外部) ' % x)
            elif t in ('puton', 'putin'):
                x, y = vmap.get('X'), vmap.get('Y')
                if c[0] == ':cons_not':
                    sp = visible.sameplace(x, y) if t == 'puton' else (visible.inside.get(x) == y)
                    if sp is True:
                        issues.append('初始已满足 cons_not(task %s %s %s) ' % (t, x, y))
            continue

        # info 类约束
        if '?' in var.get('X', []) or (var.get('X') == []):
            pass
        xid = var['X'][0] if var.get('X') else None
        yid = var['Y'][0] if var.get('Y') else None
        vmap = {'X': xid, 'Y': yid}
        # 多候选时逐个看(保守: 只要有一个候选使初始状态破坏约束就报)
        cands = []
        for xi in (var.get('X') or [None]):
            for yi in (var.get('Y') or [None] if 'Y' in var else [None]):
                cands.append({'X': xi, 'Y': yi})
        for vm in cands:
            tv = truth.ev_info(pred, [a for a in body if isinstance(a, str)], vm)
            if tv is None:
                continue
            want = True if c[0] == ':cons_notnot' else False
            if tv != want:
                issues.append('初始状态%s约束 %s(%s %s) [真值=%s, 期望=%s]' %
                              ('破坏' if tv != want else '', c[0], pred,
                               ' '.join('%s=%s' % (k, v) for k, v in vm.items() if v), tv, want))
    return issues


if __name__ == '__main__':
    for d in sys.argv[1:]:
        files = sorted(glob.glob(os.path.join(d, '*.xml')))
        bad = 0
        print("=== %s (%d题) ===" % (d, len(files)))
        for f in files:
            try:
                iss = check(f)
            except Exception as e:
                print("  [解析失败] %s: %s" % (f, e)); continue
            if iss:
                bad += 1
                print("  [初始破坏约束] %s" % os.path.basename(f))
                for i in sorted(set(iss))[:4]:
                    print("      - %s" % i)
        print("  -> 有问题: %d / %d\n" % (bad, len(files)))