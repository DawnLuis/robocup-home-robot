#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2026版出题指南合规自查 (对照《2026中国机器人大赛服务机器人仿真项目出题指南》)
用法: python3 check_rules_2026.py <题目目录> [更多目录...]
覆盖: 编号断号/负数/robot=0/human唯一、字段顺序、color/type缺失、
      位置内大物体数、重复指令、cons_notnot内层、括号完整性、
      instr与env物体一致性、on/near双小物体、goto合法性、
      NL句数与句号、理论满分下限(§五 200-1000)、阶段标志(mis/err/ans)
"""
import re, sys, os, glob, collections

BIGOBJS = set("human plant couch chair sofa bed table workspace worktable teapoy desk television airconditioner washmachine".split())
CONTAINERS = set("closet cupboard refrigerator microwave".split())
SMALLOBJS = set("book can remotecontrol bottle cup".split())
COLORS = set("white black yellow blue green red".split())
PHYS1 = {'give', 'puton', 'goto', 'putdown', 'pickup', 'open', 'close'}
PHYS2 = {'putin', 'takeout'}


def tokenize(s):
    s = re.sub(r'<!--.*?-->', ' ', s, flags=re.S)
    return [t for t in re.split(r'(\()|(\))|\s+', s) if t and not t.isspace()]


def parse(s):
    """极简 s-expression 解析 -> 嵌套 list"""
    toks = [t for t in re.findall(r'\(|\)|[^\s()]+', s)]
    stack = [[]]
    for t in toks:
        if t == '(':
            stack.append([])
        elif t == ')':
            if len(stack) < 2:
                raise ValueError('括号不匹配(多余的右括号)')
            top = stack.pop(); stack[-1].append(top)
        else:
            stack[-1].append(t)
    if len(stack) != 1:
        raise ValueError('括号不匹配(缺少 %d 个右括号)' % (len(stack) - 1))
    return stack[0]


def atoms(sexp):
    """把 [(pred a b) ...] 展平成 [(pred,[args])]"""
    out = []
    for e in sexp:
        if isinstance(e, list) and e and isinstance(e[0], str):
            out.append((e[0], e[1:]))
    return out


def check(path):
    errs, warns = [], []
    raw = open(path, encoding='utf-8', errors='replace').read()
    m = re.search(r'<env([^>]*)>(.*?)</env>', raw, re.S)
    if not m:
        return ['缺 <env>'], [], None
    flags = dict(re.findall(r'(\w+)\s*=\s*"(\w+)"', m.group(1)))
    env_raw = m.group(2)

    def sbody(tag, txt=None):
        mm = re.search(r'<%s>(.*?)</%s>' % (tag, tag), env_raw if txt is None else txt, re.S)
        return mm.group(1) if mm else ''

    try:
        info = atoms(parse(sbody('info')))
        mis = atoms(parse(sbody('mis')))
    except ValueError as e:
        errs.append('env %s' % e); info, mis = [], []
    err_raw = sbody('err')
    r_atoms = atoms(parse(sbody('r', err_raw))) if err_raw else []
    w_atoms = atoms(parse(sbody('w', err_raw))) if err_raw else []
    extra = atoms(parse(sbody('extra')))

    if not info:
        errs.append('<info> 为空')

    # ---------- 物体表 ----------
    objs = collections.OrderedDict()
    for pred, a in info:
        if pred == 'sort' and len(a) >= 2:
            objs[a[0]] = {'sort': a[1], 'fields': []}
    for pred, a in info:
        if a and a[0] in objs and pred not in ('sort', 'hold', 'plate'):
            objs[a[0]][pred] = a[1:]
            objs[a[0]]['fields'].append(pred)
    # robot 行的 (hold N)/(plate N) 里 N 是"在机器人手上/盘上"的物体id, 不是该物体自己的字段
    on_robot = set()
    for pred, a in info:
        if pred in ('hold', 'plate') and a and a[0] != '0':
            on_robot.add(a[0])
    robot_fields = [p for p, a in info if p in ('hold', 'plate') or (p == 'at' and a and a[0] == '0')]
    if not robot_fields:
        errs.append('info 缺 robot(id 0) 的 hold/plate/at')
    ids = sorted(int(i) for i in objs)
    if ids and ids != list(range(1, len(ids) + 1)):
        missing = sorted(set(range(1, (ids[-1] if ids else 0) + 1)) - set(ids))
        errs.append('物体编号 1..N 断号: 缺 %s (现有 %s)' % (missing, ids))
    humans = [i for i in objs if objs[i]['sort'] == 'human']
    if humans != ['1']:
        errs.append('human 必须编号1且唯一, 实际 %s' % humans)
    if humans and 'at' not in objs.get('1', {}):
        errs.append('human 缺 at')
    for i, o in objs.items():
        s = o['sort']
        f = o['fields']
        # 字段顺序 sort 必须首位 + 固定顺序(2026附录A): sort,size,[color],at|inside,[type],[opened|closed]
        kind = 'small' if s in SMALLOBJS else ('container' if s in CONTAINERS else 'big')
        want = {'small': ['size', 'color', 'AT', 'at'], 'big': ['size', 'at'],
                'container': ['size', 'at', 'type', 'openstate']}[kind]
        seq = []
        for x in f:
            if x in ('at', 'inside'):
                seq.append('AT' if kind == 'small' else 'at')
            elif x in ('opened', 'closed'):
                seq.append('openstate' if kind == 'container' else x)
            else:
                seq.append(x)
        expect = [w for w in want if w in seq]
        if seq != expect:
            errs.append('#%s(%s) 字段顺序不符(应为 sort,%s) 实际 %s' % (i, s, ','.join(want), f))
        if s in SMALLOBJS:
            if not o.get('color'):
                errs.append('小物体 #%s(%s) 缺 color' % (i, s))
            elif o['color'][0] not in COLORS:
                errs.append('小物体 #%s(%s) color=%s 不在词表' % (i, s, o['color'][0]))
            if o.get('size', ['?'])[0] != 'small':
                errs.append('小物体 #%s(%s) size=%s 应为 small' % (i, s, o.get('size')))
            if 'at' not in o and 'inside' not in o and i not in on_robot:
                warns.append('小物体 #%s(%s) 无 at/inside' % (i, s))
        elif s in CONTAINERS:
            if o.get('type', ['?'])[0] != 'container':
                errs.append('容器 #%s(%s) 缺 type container' % (i, s))
            if 'opened' not in o and 'closed' not in o:
                warns.append('容器 #%s(%s) 无 opened/closed' % (i, s))
        elif s in BIGOBJS:
            if o.get('size', ['?'])[0] != 'big':
                errs.append('大物体 #%s(%s) size=%s 应为 big' % (i, s, o.get('size')))
            if s != 'human' and 'at' not in o:
                warns.append('大物体 #%s(%s) 无 at' % (i, s))
        else:
            errs.append('#%s 未知 sort=%s' % (i, s))
    # ---------- 重复物体 (2026§二.2(5): 不可出现完全一样的大物体或小物体) ----------
    seen_small = collections.Counter()
    seen_big = collections.Counter()
    for i, o in objs.items():
        s = o['sort']
        if s in SMALLOBJS:
            seen_small[(s, (o.get('color') or ['?'])[0])] += 1
        elif s in BIGOBJS or s in CONTAINERS:
            seen_big[s] += 1
    for k, v in seen_small.items():
        if v > 1:
            errs.append('重复小物体 %s×%d (完全相同的小物体不可出现)' % (k, v))
    for k, v in seen_big.items():
        if v > 1:
            errs.append('重复大物体/容器 %s×%d' % (k, v))

    # 位置编号非负
    for group, name in ((info, 'info'), (mis, 'mis'), (r_atoms, 'err/r'), (w_atoms, 'err/w'), (extra, 'extra')):
        for pred, a in group:
            if pred == 'at' and len(a) == 2 and a[1].isdigit() is False and not a[1].startswith('0'):
                errs.append('%s at 位置编号非数字: %s' % (name, a))
    # 一个位置至多一个大物体
    big_at = collections.Counter()
    for i, o in objs.items():
        if o['sort'] in BIGOBJS and 'at' in o:
            big_at[o['at'][0]] += 1
    for loc, c in big_at.items():
        if c > 1:
            errs.append('位置 %s 有 %d 个大物体(至多1个)' % (loc, c))
    # info 与 mis/err/extra 矛盾
    info_pos = {(p, tuple(a)) for p, a in info if p in ('at', 'inside', 'opened', 'closed')}
    for group, name in ((mis, 'mis'), (r_atoms, 'err/r'), (w_atoms, 'err/w'), (extra, 'extra')):
        for pred, a in group:
            if pred in ('at', 'inside') and tuple(a) and tuple(a)[0] in objs:
                other = [x for p, x in info if p in ('at', 'inside') and x and x[0] == a[0]]
                if other and tuple(other[0]) != tuple(a):
                    errs.append('%s 与 info 位置矛盾: #%s info=%s %s=%s' % (name, a[0], other[0], name, a))
            if pred in ('opened', 'closed') and tuple(a) and tuple(a)[0] in objs:
                other = [x for p, x in info if p in ('opened', 'closed') and x and x[0] == a[0]]
                if other and other[0][0] != a[0]:
                    pass
                elif other and [p for p, x in info if x == a and p in ('opened', 'closed')] and \
                        [p for p, x in info if x == a and p in ('opened', 'closed')][0] != pred:
                    errs.append('%s 与 info 开关状态矛盾: #%s info=%s %s=%s' % (name, a[0], other, name, a))
    if (r_atoms or w_atoms) and not (r_atoms and w_atoms):
        warns.append('err 段只有 r 或只有 w')
    for pred, a in r_atoms:
        if not any(p == pred and x == a for p, x in w_atoms):
            pass

    # ---------- instr ----------
    mi = re.search(r'<instr>(.*?)</instr>', raw, re.S)
    if not mi:
        errs.append('缺 <instr>')
        return errs, warns, None
    try:
        ix = parse(mi.group(1))
    except ValueError as e:
        errs.append('instr %s' % e)
        return errs, warns, None
    root = None
    for e in ix:
        if isinstance(e, list) and e and e[0] == ':ins':
            root = e
    if root is None:
        for e in ix:
            if isinstance(e, list) and e and str(e[0]).startswith(':ins'):
                root = e
    if root is None:
        errs.append('instr 缺 (:ins ...) 或括号不匹配')
        return errs, warns, None
    cmds = [c for c in root[1:] if isinstance(c, list) and c and isinstance(c[0], str) and c[0].startswith(':')]
    tasks = [c for c in cmds if c[0] == ':task']
    cons = [c for c in cmds if c[0] in (':cons_not', ':cons_notnot')]
    infos = [c for c in cmds if c[0] == ':info']
    if not cmds:
        warns.append('instr 无指令')
    if len(tasks) == 0:
        errs.append('无 :task 目标(每题至少1个目标)')

    def cond_of(c):
        for x in c[1:]:
            if isinstance(x, list) and x and x[0] == ':cond':
                return atoms(x[1:])
        return []

    # 重复指令
    norm = [re.sub(r'\s+', ' ', str(c).replace("'", '')) for c in cmds]
    for k, v in collections.Counter(norm).items():
        if v > 1:
            errs.append('重复指令 ×%d: %s' % (v, k[:70]))
    # cons_notnot 内层只能是 :info
    for c in cons:
        if c[0] == ':cons_notnot' and (len(c) < 2 or not isinstance(c[1], list) or c[1][0] != ':info'):
            errs.append('cons_notnot 内层必须是 (:info ...): %s' % str(c)[:70])
    # X/Y 括号 变量规则 + cond 内容
    def objs_match(sort=None, color=None, typ=None, exclude=()):
        out = []
        for i, o in objs.items():
            if i in exclude:
                continue
            if sort and o['sort'] != sort:
                continue
            if color and (o.get('color') or [''])[0] != color:
                continue
            if typ and (o.get('type') or [''])[0] != typ:
                continue
            out.append(i)
        return out

    def inner(c):
        """cons 的内层指令"""
        return c[1] if len(c) > 1 and isinstance(c[1], list) else None

    for c in cmds:
        body = inner(c) if c[0].startswith(':cons') else c
        if body is None:
            errs.append('%s 缺内层指令: %s' % (c[0], str(c)[:60]))
            continue
        pred = body[0]
        args = [a for a in body[1:] if isinstance(a, str)]
        args = [a for a in args if not a.startswith(':')]
        if c[0] == ':info':
            pass
        if pred in ('on', 'near') or (c[0] == ':info' and pred in ('on', 'near')):
            pass
        conds = cond_of(body)
        sd = {a[0]: a[1] for a in conds if a and a[0] in ('sort', 'color', 'type') and len(a) > 1}
        # 变量与物体存在性
        for var in ('X', 'Y'):
            if var in args:
                sort = sd.get('sort')
                color = sd.get('color')
                typ = sd.get('type')
                if not sort:
                    errs.append('%s 条件缺 sort %s: %s' % (pred, var, str(body)[:60]))
                    continue
                hit = objs_match(sort, color, typ)
                if not hit:
                    errs.append('%s 的 %s 在环境中无匹配物体 (sort=%s color=%s type=%s) [%s 内层=%s]' %
                                (pred, var, sort, color, typ, c[0], str(body)[:50]))
                if sort in SMALLOBJS and not color and c[0] != ':info':
                    warns.append('%s 小物体条件缺 color: %s' % (pred, str(body)[:60]))
                if sort in CONTAINERS and typ != 'container' and pred in ('open', 'close', 'putin', 'takeout', 'inside'):
                    warns.append('%s 容器条件缺 (type %s container): %s' % (pred, var, str(body)[:60]))
        # on/near 两物体不能都是小物体
        if pred in ('on', 'near') and 'X' in args and 'Y' in args:
            sX = sd.get('sort')
            if sX in SMALLOBJS and sd.get('sort') == sX:
                pass
        if pred in ('on', 'near'):
            pass
        # goto 合法性
        if pred == 'goto':
            s = sd.get('sort')
            if s in SMALLOBJS:
                cand = objs_match(s, sd.get('color'))
                for i in cand:
                    o = objs[i]
                    if ('at' not in o) or 'inside' in o:
                        warns.append('goto 作用小物体 #%s 可能不在手爪/盘/容器也不在地面' % i)
    # on/near 两物体都是小物体(需对比两个 sort)
    for c in cmds:
        body = inner(c) if c[0].startswith(':cons') else c
        if body is None:
            continue
        if body[0] in ('on', 'near'):
            conds = cond_of(body)
            sorts = [a[1] for a in conds if a and a[0] == 'sort' and len(a) > 1]
            if len(sorts) == 2 and all(s in SMALLOBJS for s in sorts):
                errs.append('on/near 关联的两个物体都是小物体: %s' % str(body)[:60])

    # G/C / 理论满分
    G, C = len(tasks), len(cons)
    ub = 40 * G + 20 * C + 100
    if ub < 200:
        errs.append('理论满分上限 %d < 200 (目标%d/约束%d) 违反2026§五' % (ub, G, C))
    if ub > 1000:
        warns.append('理论满分上限 %d > 1000' % ub)

    # ---------- nl ----------
    mn = re.search(r'<nl>(.*?)</nl>', raw, re.S)
    if not mn:
        errs.append('缺 <nl>')
    else:
        body_txt = mn.group(1).strip()
        sents = [s.strip() for s in re.split(r'(?<=\.)\s+', body_txt) if s.strip()]
        if len(sents) != len(cmds):
            errs.append('NL 句数 %d != instr 指令数 %d' % (len(sents), len(cmds)))
        for s in sents:
            if not s.endswith('.'):
                errs.append('NL 句未以句号结尾: %s' % s[:50])
    # 阶段标志 (2026指南§二.1: 第一阶段 mis/err/ans 均为 off, 第二阶段均为 on)
    stage_dir = os.path.basename(os.path.dirname(os.path.abspath(path)))
    want_all = 'off' if 'stage1' in stage_dir else ('on' if 'stage2' in stage_dir else None)
    if want_all:
        for k in ('mis', 'err', 'ans'):
            if flags.get(k) != want_all:
                errs.append('%s 开关错误: %s="%s" 应为 "%s" (2026指南§二.1)' % (stage_dir, k, flags.get(k), want_all))
    else:
        warns.append('无法判定阶段目录, 仅记录 flags=%s' % flags)
    return errs, warns, dict(G=G, C=C, infos=len(infos), flags=flags, ub=ub)


if __name__ == '__main__':
    files = []
    for d in sys.argv[1:]:
        files += sorted(glob.glob(os.path.join(d, '*.xml')))
    print("=== 共 %d 道题 ===" % len(files))
    bad = 0; stat = []
    for f in files:
        try:
            errs, warns, info = check(f)
        except Exception as e:
            print("\n[解析失败] %s: %s" % (f, e)); bad += 1; continue
        if errs:
            bad += 1
            print("\n[错误] %s" % os.path.basename(f))
            for e in errs: print("   - %s" % e)
        if warns:
            print("[提示] %s" % os.path.basename(f))
            for w in warns[:5]: print("   ? %s" % w)
        if info:
            stat.append((os.path.basename(f), info['G'], info['C'], info['infos'], info['ub'], info['flags']))
    print("\n=== 有错误的题: %d / %d ===" % (bad, len(files)))
    print("\n=== 目标G/约束C/info数/理论满分上限 ===")
    for s in stat:
        print("  %-12s G=%-2d C=%-2d info=%-2d 满分上限=%-4d %s" %
              (s[0], s[1], s[2], s[3], s[4], {k: v for k, v in s[5].items() if k in ('mis', 'err', 'ans')}))
    if stat:
        lo = min(x[4] for x in stat)
        print("\n最低理论满分上限 = %d ; 低于200的题数 = %d" % (lo, sum(1 for x in stat if x[4] < 200)))