#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
严格对照《2026中国机器人大赛服务机器人仿真项目出题指南》【附录B 指令语言格式】逐条比对
唯一标准 = 出题指南(不参考平台自带题库)

附录B 规定的条件集合(顺序敏感):
  INFO :info (on X Y)      -> (:cond (sort X *) (color X *) (sort Y *))
       :info (near X Y)    -> (:cond (sort X *) (color X *) (sort Y *))
       :info (plate X)     -> (:cond (sort X *) (color X *))
       :info (inside X Y)  -> (:cond (sort X *) (color X *) (sort Y *))     <-- Y 不带 type
       :info (opened X)    -> (:cond (sort X *))
       :info (closed X)    -> (:cond (sort X *))
  TASK :task (give human X)-> (:cond (sort X *) (color X *))                <-- 首参必须是字面 human
       :task (puton X Y)   -> (:cond (sort X *) (color X *) (sort Y *))     <-- Y 不带 type
       :task (goto X)      -> (:cond (sort X *))
       :task (putdown X)   -> (:cond (sort X *) (color X *))
       :task (pickup X)    -> (:cond (sort X *) (color X *))
       :task (open X)      -> (:cond (sort X *) (type X container))         <-- X 不带 color
       :task (close X)     -> (:cond (sort X *) (type X container))
       :task (putin X Y)   -> (:cond (sort X *) (color X *) (sort Y *) (type Y container))
       :task (takeout X Y) -> (:cond (sort X *) (color X *) (sort Y *) (type Y container))
  CONS :cons_not/:cons_notnot 内层沿用上面 task/info 的同名模板

同时校验:
  - 容器在 env info 中的描述语法: (sort N *) (size N big) (at N *) (type N container) (opened|closed N)
  - 第一阶段 mis/err/ans 三开关必须全为 off (指南§二.1 / 附录D)

用法: python3 check_appendixB_2026.py <题目目录>
"""
import re, sys, os, glob

TASK_COND = {
    'give':     [('sort', 'X'), ('color', 'X')],
    'puton':    [('sort', 'X'), ('color', 'X'), ('sort', 'Y')],
    'goto':     [('sort', 'X')],
    'putdown':  [('sort', 'X'), ('color', 'X')],
    'pickup':   [('sort', 'X'), ('color', 'X')],
    'open':     [('sort', 'X'), ('type', 'X')],
    'close':    [('sort', 'X'), ('type', 'X')],
    'putin':    [('sort', 'X'), ('color', 'X'), ('sort', 'Y'), ('type', 'Y')],
    'takeout':  [('sort', 'X'), ('color', 'X'), ('sort', 'Y'), ('type', 'Y')],
}
INFO_COND = {
    'on':     [('sort', 'X'), ('color', 'X'), ('sort', 'Y')],
    'near':   [('sort', 'X'), ('color', 'X'), ('sort', 'Y')],
    'plate':  [('sort', 'X'), ('color', 'X')],
    'inside': [('sort', 'X'), ('color', 'X'), ('sort', 'Y')],
    'opened': [('sort', 'X')],
    'closed': [('sort', 'X')],
}
SMALL = set("book can remotecontrol bottle cup".split())
BIG = set("human plant couch chair sofa bed table workspace worktable teapoy desk television airconditioner washmachine".split())
CONT = set("closet cupboard refrigerator microwave".split())

TASKV = set(TASK_COND)
INFOV = set(INFO_COND)


def top_cmds(text):
    out, depth, start = [], 0, None
    for i, ch in enumerate(text):
        if ch == '(':
            depth += 1
            if depth == 2 and start is None:
                start = i
        elif ch == ')':
            depth -= 1
            if depth == 1 and start is not None:
                out.append(text[start:i + 1])
                start = None
    return out


def parse_cmd(cmd):
    """返回 (outer, kind, pred, args, conds)  kind = 'task'/'info'"""
    m = re.match(r'\((:[a-z_]+)\s+', cmd)
    outer = m.group(1)
    s = cmd
    if outer in (':cons_not', ':cons_notnot'):
        m2 = re.match(r'\(:cons_not(?:not)?\s+\(:(info|task)\s+\((\w+)([^()]*)\)', s)
        if not m2:
            return outer, None, None, None, None
        kind, pred = m2.group(1), m2.group(2)
        args = m2.group(3).split()
    else:
        m2 = re.match(r'\(:(info|task)\s+\((\w+)([^()]*)\)', s)
        if not m2:
            return outer, None, None, None, None
        kind, pred = m2.group(1), m2.group(2)
        args = m2.group(3).split()
    conds = []
    mc = re.search(r'\(:cond((?:\s*\([^()]*\))*)\s*\)', s)
    if mc:
        for mm in re.finditer(r'\((\w+)\s+([XY])\s*([^*)]*)\)', mc.group(1)):
            conds.append((mm.group(1), mm.group(2)))
    return outer, kind, pred, args, conds


def check(path):
    errs = []
    raw = open(path, encoding='utf-8', errors='replace').read()

    # --- mis/err/ans 开关(指南§二.1: 第一阶段全off, 第二阶段全on) ---
    m = re.search(r'<env([^>]*)>', raw)
    flags = dict(re.findall(r'(\w+)\s*=\s*"(\w+)"', m.group(1)))
    sdir = os.path.basename(os.path.dirname(os.path.abspath(path)))
    want = 'off' if 'stage1' in sdir else ('on' if 'stage2' in sdir else None)
    if want:
        for k in ('mis', 'err', 'ans'):
            if flags.get(k) != want:
                errs.append('开关错误: %s="%s" 该阶段必须为 "%s"(指南§二.1)' % (k, flags.get(k), want))

    # --- 容器在 info 中的描述语法(指南附录A + §二.6) ---
    info = re.search(r'<info>(.*?)</info>', raw, re.S).group(1)
    for line in info.splitlines():
        line = line.strip()
        if not line or 'container' not in line:
            continue
        got = re.findall(r'\((\w+)\s', line)
        want = ['sort', 'size', 'at', 'type', 'opened'] if 'opened' in got else ['sort', 'size', 'at', 'type', 'closed']
        if got != want:
            errs.append('容器描述语法不符(附录A 应为 %s): %s' % (','.join(want), line[:70]))
        if not re.search(r'\(type \d+ container\)', line):
            errs.append('容器缺 (type N container): %s' % line[:70])

    # --- 逐条指令对照附录B ---
    instr = re.search(r'<instr>(.*?)</instr>', raw, re.S).group(1)
    for cmd in top_cmds(instr):
        outer, kind, pred, args, conds = parse_cmd(cmd)
        if kind is None:
            errs.append('指令解析失败: %s' % cmd[:60])
            continue
        tmpl = (TASK_COND if kind == 'task' else INFO_COND).get(pred)
        if tmpl is None:
            errs.append('附录B 无此 %s 谓词: %s' % (kind, cmd[:60]))
            continue
        if conds != tmpl:
            errs.append('%s (%s) 条件不符附录B\n        期望 %s\n        实际 %s\n        原文 %s'
                        % (outer, pred, tmpl, conds, cmd[:80]))
        # give 首参必须字面 human
        if pred == 'give':
            if not args or args[0] != 'human':
                errs.append('give 的首个参数必须是字面 human(附录B: give human X): %s' % cmd[:60])
            if args[1:] != ['X']:
                errs.append('give 变量应为 X: %s' % cmd[:60])
        else:
            want_args = ['X'] if not any(c[1] == 'Y' for c in tmpl) else ['X', 'Y']
            if args != want_args:
                errs.append('%s 变量应为 %s, 实际 %s: %s' % (pred, want_args, args, cmd[:60]))
        # cons_notnot 内层只能是 :info(指南§三.6)
        if outer == ':cons_notnot' and kind != 'info':
            errs.append('(:cons_notnot 内层必须 :info: %s' % cmd[:60])
        # §三.6: 一条指令不能同时出现两个小物体(含 on/near 关联的两物体不能都是小物体)
        sorts = [m2.group(1).strip() for m2 in re.finditer(r'\(sort\s+[XY]\s+([^)]*)\)', cmd)]
        if len(sorts) == 2 and all(s in SMALL for s in sorts):
            errs.append('§三.6 一条指令不能同时出现两个小物体: %s' % cmd[:70])
    return errs


if __name__ == '__main__':
    files = []
    for d in sys.argv[1:]:
        files += sorted(glob.glob(os.path.join(d, '*.xml')))
    print("=== 附录B 严格比对 + 容器语法 + mis开关: %d 道题 ===" % len(files))
    bad = 0
    for f in files:
        e = check(f)
        if e:
            bad += 1
            print("\n[不符] %s" % os.path.basename(f))
            for x in e:
                print("   - %s" % x)
    print("\n=== 不符附录B 的题: %d / %d ===" % (bad, len(files)))