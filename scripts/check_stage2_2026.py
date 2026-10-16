#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第二阶段(stage2) 【mis / err / extra 段】专项检查
唯一标准 = 《2026中国机器人大赛服务机器人仿真项目出题指南》

逐条覆盖:
  §二.1 第二阶段 mis/err/ans 均为 on
  §二.3 mis 部分可以有: 小物体的 at(或 inside)、大物体的 at、robot 的 plate、容器的 opened(或 closed)
  §二.4 err 部分可以有(正确信息写 r, 错误信息写 w):
        (1) 小物体 at/inside   : r=at -> w∈{at,inside} ; r=inside -> w∈{at,inside}
        (2) 大物体 at          : r=at -> w=at
        (3) robot 的 plate     : r=plate -> w∈{at,inside}
        (4) 容器 opened/closed : r=opened -> w=closed ; r=closed -> w=opened
        ★ w 中的错误信息不能与 info 中已给出的信息相矛盾
        ★ r 是正确信息, 更不能与 info 矛盾
  §二.5 extra 部分: 字段白名单 + 其中每条信息必须在 instr 的 info 中指出
  §二.2 注(2) info 中省略了位置的小物体, 其位置必须出现在 mis 或 err 段(否则等于凭空消失)
  另: w 必须与 r 不同(否则不是"错误信息"); 所有引用的物体/容器编号必须存在且类型正确

用法: python3 check_stage2_2026.py <stage2目录>
"""
import re, sys, os, glob, collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_rules_2026 as CR

SMALL, CONT, BIG = CR.SMALLOBJS, CR.CONTAINERS, CR.BIGOBJS
MIS_OBJ_PRED = {'at', 'inside'}          # mis 里可作用在物体上的
ERR_FORBID_INFO = {'at', 'inside', 'opened', 'closed', 'plate'}


def seg(raw, tag):
    m = re.search(r'<%s>(.*?)</%s>' % (tag, tag), raw, re.S)
    return m.group(1) if m else ''


def rd(raw):
    """读题目 -> dict"""
    envm = re.search(r'<env([^>]*)>(.*?)</env>', raw, re.S)
    flags = dict(re.findall(r'(\w+)\s*=\s*"(\w+)"', envm.group(1)))
    env = envm.group(2)
    info = CR.atoms(CR.parse(seg(env, 'info')))
    objs = collections.OrderedDict()
    for p, a in info:
        if p == 'sort' and len(a) >= 2:
            objs[a[0]] = {'sort': a[1], 'f': {}}
    for p, a in info:
        if p in ('sort', 'hold', 'plate') or not a or a[0] == '0':
            continue
        if a[0] in objs:
            objs[a[0]]['f'][p] = a[1:]
    robot = {'hold': '0', 'plate': '0', 'at': None}
    for p, a in info:
        if p == 'hold' and a:
            robot['hold'] = a[0]          # (hold N) 的 N 就是"在手上的物体 id", 0 = 空手
        elif p == 'plate' and a:
            robot['plate'] = a[0]         # (plate N) 同理
        elif p == 'at' and a and a[0] == '0':
            robot['at'] = a[1] if len(a) > 1 else None
    return flags, objs, robot, \
        CR.atoms(CR.parse(seg(env, 'mis'))), \
        CR.atoms(CR.parse(seg(env, 'r'))), \
        CR.atoms(CR.parse(seg(env, 'w'))), \
        CR.atoms(CR.parse(seg(env, 'extra')))


def kind_of(objs, i):
    if i not in objs:
        return None
    s = objs[i]['sort']
    return 'small' if s in SMALL else ('container' if s in CONT else ('big' if s in BIG else None))


def check(path):
    errs = []
    raw = open(path, encoding='utf-8', errors='replace').read()
    flags, objs, robot, mis, r_at, w_at, extra = rd(raw)

    # §二.1
    for k in ('mis', 'err', 'ans'):
        if flags.get(k) != 'on':
            errs.append('§二.1 第二阶段 %s 必须 "on", 实际 "%s"' % (k, flags.get(k)))

    # 收集 info 里已给出的位置/开关
    info_pos = {}
    for i, o in objs.items():
        for p in ('at', 'inside', 'opened', 'closed'):
            if p in o['f']:
                info_pos[i] = (p, tuple(o['f'][p]))
    if robot.get('plate', '0') != '0':
        info_pos[robot['plate']] = ('plate',)

    def exists(i, ctx):
        if i not in objs:
            errs.append('%s 引用了不存在的物体编号 %s' % (ctx, i))
            return False
        return True

    # ---------- §二.3 mis ----------
    for pred, a in mis:
        if not a:
            continue
        i = a[0]
        if pred in MIS_OBJ_PRED:
            if not exists(i, 'mis'):
                continue
            k = kind_of(objs, i)
            if k not in ('small', 'big'):
                errs.append('§二.3 mis 的 %s 只能用于小物体/大物体, #%s 是 %s' % (pred, i, objs[i]['sort']))
            if pred == 'inside' and k == 'small' and len(a) > 1:
                if a[1] not in objs or kind_of(objs, a[1]) != 'container':
                    errs.append('§二.3 mis (inside %s %s): %s 不是容器' % (i, a[1], a[1]))
        elif pred == 'plate':
            if i not in ('0',) and i != robot.get('plate'):
                errs.append('§二.3 mis 的 plate 字段应针对 robot(保持 (plate 0) 或与 info 一致), 实际 %s' % (a,))
        elif pred in ('opened', 'closed'):
            if exists(i, 'mis') and kind_of(objs, i) != 'container':
                errs.append('§二.3 mis 的 %s 只能用于容器, #%s 是 %s' % (pred, i, objs[i]['sort']))
        else:
            errs.append('§二.3 mis 出现不允许的字段 %s: %s' % (pred, a))

    # ---------- §二.4 err ----------
    if flags.get('err') == 'on':
        if not r_at or not w_at:
            errs.append('§二.4 err="on" 但 r 或 w 为空')
    rmap = collections.OrderedDict()
    for pred, a in r_at:
        rmap.setdefault(a[0], []).append((pred, a))
    wmap = collections.OrderedDict()
    for pred, a in w_at:
        wmap.setdefault(a[0], []).append((pred, a))

    for i, rl in rmap.items():
        if not exists(i, 'err/r'):
            continue
        k = kind_of(objs, i)
        for pred, a in rl:
            if pred not in ('at', 'inside', 'plate', 'opened', 'closed'):
                errs.append('§二.4 err/r 不允许的字段 %s: %s' % (pred, a))
                continue
            # r 本身不能与 info 矛盾
            if i in info_pos and info_pos[i] != (pred, tuple(a)):
                errs.append('§二.4 err/r 与 info 矛盾: #%s info=%s, r=%s' % (i, info_pos[i], (pred, tuple(a))))
            if pred == 'inside' and len(a) > 1 and (a[1] not in objs or kind_of(objs, a[1]) != 'container'):
                errs.append('§二.4 err/r (inside %s %s): %s 不是容器' % (i, a[1], a[1]))
            if pred in ('opened', 'closed') and k != 'container':
                errs.append('§二.4 err/r 的 %s 只能用于容器, #%s 是 %s' % (pred, i, objs[i]['sort']))
        wl = wmap.get(i, [])
        if not wl:
            errs.append('§二.4 err: #%s 有 r 却无对应 w(r/w 必须成对)' % i)
            continue
        for wpred, wa in wl:
            rpreds = [p for p, _ in rl]
            # 逐条对照指南允许的 r/w 组合
            ok = False
            for rpred, ra in rl:
                if rpred == 'at' and wpred in ('at', 'inside'):
                    ok = True
                elif rpred == 'inside' and wpred in ('at', 'inside'):
                    ok = True
                elif rpred == 'plate' and wpred in ('at', 'inside'):
                    ok = True
                elif rpred == 'opened' and wpred == 'closed':
                    ok = True
                elif rpred == 'closed' and wpred == 'opened':
                    ok = True
            if not ok:
                errs.append('§二.4 r/w 组合非法: #%s r=%s -> w=%s (指南只允许 at→{at,inside}/inside→{at,inside}/'
                            'plate→{at,inside}/opened→closed/closed→opened)' % (i, rl, (wpred, wa)))
            if wpred == 'at' and (wpred, tuple(wa)) in [(p, tuple(x)) for p, x in rl]:
                pass
            # w != r
            for rpred, ra in rl:
                if rpred == wpred and tuple(ra) == tuple(wa):
                    errs.append('§二.4 #%s 的 w 与 r 完全相同(不是"错误信息"): %s' % (i, (wpred, wa)))
            # w 不能与 info 矛盾
            if i in info_pos and info_pos[i] == (wpred, tuple(wa)):
                errs.append('§二.4 err/w 与 info 已给信息相同(等于没误导, 且指南禁止 w 与 info 矛盾): #%s %s' % (i, (wpred, wa)))
            if wpred == 'inside' and len(wa) > 1 and (wa[1] not in objs or kind_of(objs, wa[1]) != 'container'):
                errs.append('§二.4 err/w (inside %s %s): %s 不是容器' % (i, wa[1], wa[1]))
            if wpred in ('opened', 'closed') and kind_of(objs, i) != 'container':
                errs.append('§二.4 err/w 的 %s 只能用于容器, #%s 是 %s' % (wpred, i, objs[i]['sort']))
    for i in wmap:
        if i not in rmap:
            errs.append('§二.4 err: #%s 有 w 却无对应 r' % i)

    # ---------- §二.2 注(2): info 省略位置的小物体, 位置必须出现在 mis 或 err ----------
    mis_ids = {a[0] for p, a in mis if p in ('at', 'inside')}
    err_ids = set(rmap) | set(wmap)
    on_robot = set()
    if robot.get('hold', '0') != '0':
        on_robot.add(robot['hold'])
    if robot.get('plate', '0') != '0':
        on_robot.add(robot['plate'])
    for i, o in objs.items():
        if kind_of(objs, i) != 'small':
            continue
        if 'at' in o['f'] or 'inside' in o['f'] or i in on_robot:
            continue
        if i not in mis_ids and i not in err_ids:
            errs.append('§二.2注2 小物体 #%s(%s) 的位置既不在 info, 也不在 mis/err -> 信息凭空消失' % (i, o['sort']))

    # ---------- §二.5 extra ----------
    instr = seg(raw, 'instr')
    for pred, a in extra:
        i = a[0] if a else None
        if pred in MIS_OBJ_PRED:
            if i and (i not in objs or kind_of(objs, i) != 'small'):
                errs.append('§二.5 extra 的 %s 只能用于小物体: %s' % (pred, a))
        elif pred == 'plate':
            pass
        elif pred in ('opened', 'closed'):
            if i and (i not in objs or kind_of(objs, i) != 'container'):
                errs.append('§二.5 extra 的 %s 只能用于容器: %s' % (pred, a))
        else:
            errs.append('§二.5 extra 出现不允许的字段 %s: %s' % (pred, a))
        # 每条 extra 信息必须在 instr 的 info 中指出
        tgt = i
        if tgt:
            pat = r'\(:info\s+\(%s\s+[XY]\b' % pred
            if not re.search(pat, instr.replace('\n', ' ')):
                errs.append('§二.5 extra 的信息 %s 未在 instr 的 info 中指出' % (a,))

    # ---------- §三.2 / §二.6: instr 的 (:info ...) 必须与 env 真实状态一致 ----------
    # 真实状态 = info 的位置 + mis 的位置 + err/r(正确信息);  err/w 是给机器人的假信息, 不算真实
    pos = {}
    for i, o in objs.items():
        if 'at' in o['f']:
            pos[i] = ('at', o['f']['at'][0])
        elif 'inside' in o['f']:
            pos[i] = ('inside', o['f']['inside'][0])
    for i in on_robot:
        pos.setdefault(i, ('robot',))
    for group in (mis, r_at):
        for p, a in group:
            if p in ('at', 'inside') and a and a[0] not in pos:
                pos[a[0]] = (p, a[1] if len(a) > 1 else None)
    cstate = {}
    for i, o in objs.items():
        if kind_of(objs, i) == 'container':
            if 'opened' in o['f']:
                cstate[i] = 'opened'
            elif 'closed' in o['f']:
                cstate[i] = 'closed'
    for group in (mis, r_at):
        for p, a in group:
            if p in ('opened', 'closed') and a:
                cstate[a[0]] = p

    def locof(i, d=0):
        if d > 6:
            return None
        p = pos.get(i)
        if p is None:
            return None
        if p[0] == 'at':
            return p[1]
        if p[0] == 'inside':
            return locof(p[1], d + 1)
        if p[0] == 'robot':
            return robot.get('at')
        return None

    def match_objs(conds):
        d = {}
        for p, a in conds:
            if len(a) >= 2 and a[0] in ('X', 'Y'):
                d[a[0]] = a[1]
        hits = []
        for i, o in objs.items():
            if d.get('sort') and o['sort'] != d['sort']:
                continue
            if d.get('color') and (o['f'].get('color') or [None])[0] != d['color']:
                continue
            hits.append(i)
        return hits

    for cm in re.finditer(r'\(:info\s+\((\w+)([^()]*)\)\s+\(:cond((?:\s*\([^()]*\))*)\s*\)\)', instr):
        pred, raw_args = cm.group(1), cm.group(2).split()
        conds = [(m.group(1), m.group(2).split()) for m in
                 re.finditer(r'\((\w+)\s+([^()]*)\)', cm.group(3))]
        xhits = match_objs(conds)
        if not xhits:
            continue
        ok = False
        for X in xhits:
            if pred in ('on', 'near'):
                yh = [a[1] for p, a in conds if p == 'sort' and len(a) > 1 and a[0] == 'Y']
                if not yh:
                    continue
                yhits = [i for i, o in objs.items() if o['sort'] == yh[0]]
                if yhits and locof(X) is not None and locof(X) == locof(yhits[0]):
                    ok = True
            elif pred == 'inside':
                yh = [a[1] for p, a in conds if p == 'sort' and len(a) > 1 and a[0] == 'Y']
                yhits = [i for i, o in objs.items() if o['sort'] == yh[0]] if yh else []
                if yhits and pos.get(X, (None,))[0] == 'inside' and pos[X][1] == yhits[0]:
                    ok = True
            elif pred == 'plate':
                if robot.get('plate') == X:
                    ok = True
            elif pred in ('opened', 'closed'):
                if cstate.get(X) == pred:
                    ok = True
        if not ok:
            errs.append('§三.2/§二.6 instr 的 (:info (%s %s) (:cond %s)) 与环境真实状态不一致'
                        % (pred, ' '.join(raw_args), ' '.join('(%s %s)' % (p, ' '.join(a)) for p, a in conds)))
    return errs


if __name__ == '__main__':
    files = []
    for d in sys.argv[1:]:
        files += sorted(glob.glob(os.path.join(d, '*.xml')))
    print("=== 第二阶段 mis/err/extra 专项检查: %d 道题 ===" % len(files))
    bad = 0
    for f in files:
        e = check(f)
        if e:
            bad += 1
            print("\n[不符] %s" % os.path.basename(f))
            for x in e:
                print("   - %s" % x)
    print("\n=== 不符 §二.3/§二.4/§二.5 的题: %d / %d ===" % (bad, len(files)))