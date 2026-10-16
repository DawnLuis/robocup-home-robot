#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2026 提交前【语法/格式】专项检查
对照《2026中国机器人大赛服务机器人仿真项目出题指南》附录A(物体字段格式) + 附录B(指令格式)

检查项:
  1. XML 良构性(ElementTree 解析) + 文件头声明 + 根元素 <test>
  2. env/instr/nl 各段 s-expression 括号平衡(逐段报行号)
  3. 附录A 字段顺序: 小物体 sort,size,color,at|inside ; 大物体 sort,size,at ;
     容器 sort,size,at,type,opened|closed ; sort 必须居首位
  4. 附录B 括号数: cons 指令最后四个括号, 其他指令最后三个括号
  5. 附录B 指令谓词白名单 + :cond 内 (sort/color/type) 条件顺序
  6. X/Y 变量规则: 一个物体用 X, 两个物体 X 在前 Y 在后, 均大写
用法: python3 check_syntax_2026.py <题目目录> [...]
"""
import re, sys, os, glob, xml.etree.ElementTree as ET

SMALL = set("book can remotecontrol bottle cup".split())
BIG = set("human plant couch chair sofa bed table workspace worktable teapoy desk television airconditioner washmachine".split())
CONT = set("closet cupboard refrigerator microwave".split())
COLORS = set("white black yellow blue green red".split())

INFO_PRED = {'on', 'near', 'plate', 'inside', 'opened', 'closed'}
TASK_PRED = {'give', 'puton', 'goto', 'putdown', 'pickup', 'open', 'close', 'putin', 'takeout'}
PHYS1 = {'give', 'puton', 'goto', 'putdown', 'pickup', 'open', 'close'}
PHYS2 = {'putin', 'takeout'}


def balanced(s):
    d = 0
    for ch in s:
        if ch == '(':
            d += 1
        elif ch == ')':
            d -= 1
            if d < 0:
                return False
    return d == 0


def seg_body(raw, tag):
    m = re.search(r'<%s>(.*?)</%s>' % (tag, tag), raw, re.S)
    return m.group(1) if m else None


def top_cmds(text):
    """从 instr 原文切出顶层指令文本(含 counter 括号)"""
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


def cond_items(cmd):
    """取 :cond 内的 (sort X *) 等, 按出现顺序"""
    out = []
    for m in re.finditer(r'\(:cond((?:\s*\([^()]*\))*)\s*\)', cmd):
        for mm in re.finditer(r'\((\w+)\s+([XY])\s+([^*)]+)\)', m.group(1)):
            out.append((mm.group(1), mm.group(2), mm.group(3).strip()))
    return out


def check(path):
    errs = []
    raw = open(path, encoding='utf-8', errors='replace').read()

    # 1. XML 良构
    if not raw.lstrip().startswith('<?xml'):
        errs.append('缺 XML 声明')
    try:
        root = ET.fromstring(raw)
        if root.tag != 'test':
            errs.append('根元素应为 <test>, 实际 <%s>' % root.tag)
    except ET.ParseError as e:
        errs.append('XML 不良构: %s' % e)

    # 2. 各段括号平衡
    for tag in ('info', 'mis', 'extra', 'instr'):
        body = seg_body(raw, tag)
        if body is not None and not balanced(body):
            errs.append('<%s> 内 s-expression 括号不平衡' % tag)
    for tag in ('r', 'w'):
        body = seg_body(raw, tag)
        if body is not None and body.strip() and not balanced(body):
            errs.append('<%s> 内括号不平衡' % tag)

    # 3. 附录A 字段顺序(按行)
    info = seg_body(raw, 'info') or ''
    for line in info.splitlines():
        line = line.strip()
        if not line:
            continue
        preds = re.findall(r'\((\w+)\s+([^()]*?)\)', line)
        if not preds:
            continue
        pairs = [(p, a.split()) for p, a in preds]
        sorts = [a for p, a in pairs if p == 'sort']
        if sorts:
            sid, sname = sorts[0][0], sorts[0][1]
            if pairs[0][0] != 'sort':
                errs.append('字段顺序: sort 未居首位 -> %s' % line[:60])
            if sname in SMALL:
                want = ['size', 'color', 'at'] if 'inside' not in [p for p, _ in pairs] else ['size', 'color', 'inside']
                got = [p for p, _ in pairs if p != 'sort']
                want2 = ['size', 'color'] + (['inside'] if 'inside' in got else ['at'])
                if got != want2 and set(got) == set(want2):
                    errs.append('小物体 #%s(%s) 字段顺序应为 %s, 实际 %s' % (sid, sname, want2, got))
                for p, a in pairs:
                    if p not in ('sort', 'size', 'color', 'at', 'inside') and p != 'hold':
                        errs.append('小物体 #%s(%s) 出现非法字段 %s' % (sid, sname, p))
                if 'color' in [p for p, _ in pairs]:
                    c = [a[1] for p, a in pairs if p == 'color']
                    if c and c[0] not in COLORS:
                        errs.append('小物体 #%s color=%s 不在词表' % (sid, c[0]))
            elif sname in CONT:
                want2 = ['size', 'at', 'type', 'opened'] if 'opened' in [p for p, _ in pairs] else ['size', 'at', 'type', 'closed']
                got = [p for p, _ in pairs if p != 'sort']
                if got != want2:
                    errs.append('容器 #%s(%s) 字段顺序应为 %s, 实际 %s' % (sid, sname, want2, got))
            elif sname in BIG:
                want2 = ['size', 'at']
                got = [p for p, _ in pairs if p != 'sort']
                if got != want2:
                    errs.append('大物体 #%s(%s) 字段顺序应为 %s, 实际 %s' % (sid, sname, want2, got))
            else:
                errs.append('未知 sort=%s (#%s)' % (sname, sid))

    # 4/5/6. instr
    instr = seg_body(raw, 'instr') or ''
    cmds = top_cmds(instr)
    for cmd in cmds:
        m = re.match(r'\((:[a-z_]+)', cmd)
        if not m:
            errs.append('指令未以 (:xxx 开头: %s' % cmd[:50])
            continue
        outer = m.group(1)
        if outer not in (':info', ':task', ':cons_not', ':cons_notnot'):
            errs.append('未知指令类型 %s' % outer)
            continue
        tail = len(re.search(r'\)+$', cmd).group(0)) if re.search(r'\)+$', cmd) else 0
        want_tail = 4 if outer.startswith(':cons') else 3
        if tail != want_tail:
            errs.append('%s 指令结尾应为 %d 个括号, 实际 %d 个: %s' % (outer, want_tail, tail, cmd[:60]))
        # 谓词白名单
        body = cmd
        if outer.startswith(':cons'):
            mm = re.match(r'\(:cons_not+?\s+\(:(info|task)\s+\((\w+)', cmd)
            inner_kw = mm.group(1) if mm else None
            pred = mm.group(2) if mm else None
            if inner_kw == 'task' and pred not in TASK_PRED:
                errs.append('cons 内层 task 谓词非法: %s' % cmd[:60])
            if inner_kw == 'info' and pred not in INFO_PRED:
                errs.append('cons 内层 info 谓词非法: %s' % cmd[:60])
            if inner_kw == 'task':
                body = re.sub(r'^\(:cons_not+?\s+\(:task\s+', '(:task ', cmd)
                body = re.sub(r'\)$', '', body)
        else:
            pred = re.match(r'\(:(?:info|task)\s+\((\w+)', cmd)
            pred = pred.group(1) if pred else None
            if outer == ':info' and pred not in INFO_PRED:
                errs.append('info 谓词非法: %s' % cmd[:60])
            if outer == ':task' and pred not in TASK_PRED:
                errs.append('task 谓词非法: %s' % cmd[:60])
        # X/Y 变量
        args = re.findall(r'\b([A-Z])\b', re.sub(r'\(:cond.*', '', cmd, flags=re.S))
        if args:
            if args != sorted(args) or args not in (['X'], ['X', 'Y']):
                errs.append('X/Y 变量规则异常(应 X 或 X,Y 且大写不互换): %s -> %s' % (cmd[:50], args))
        # :cond 顺序 (sort,color,type): X 的 sort 在 X 的 color 前, Y 的 sort 在 Y 的 type 前
        ci = cond_items(cmd)
        order = [c[0] for c in ci]
        ok = order in (['sort'], ['sort', 'color'], ['sort', 'sort'], ['sort', 'color', 'sort'],
                       ['sort', 'sort', 'type'], ['sort', 'color', 'sort', 'type'],
                       ['sort', 'type'], ['sort', 'color', 'type'], [])
        if not ok:
            errs.append('(:cond 内条件顺序异常 %s: %s' % (order, cmd[:50]))
    return errs


if __name__ == '__main__':
    files = []
    for d in sys.argv[1:]:
        files += sorted(glob.glob(os.path.join(d, '*.xml')))
    print("=== 语法/格式专项检查: %d 道题 ===" % len(files))
    bad = 0
    for f in files:
        e = check(f)
        if e:
            bad += 1
            print("\n[语法/格式错误] %s" % os.path.basename(f))
            for x in e:
                print("   - %s" % x)
    print("\n=== 有语法/格式错误的题: %d / %d ===" % (bad, len(files)))