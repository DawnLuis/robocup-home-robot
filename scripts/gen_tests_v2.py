#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
出题修复生成器 v2 (2026-10-12)
在 gen_stage1.py 的30个模板基础上做三类修复, 输出到 目标目录:
  A. 约束初始态修复: 让每个 cons 在初始状态就"该成立的成立/该不成立的不成立"
     (2026指南: 一开始的环境状态就破坏了约束 = 错误; 平台 forcons.lp/testDevil.lp 语义)
  B. 冲突约束改写: cons_notnot 保护的物体被 task 搬动 => 直接互斥(UNSAT), 改写到不冲突的载体
  C. 理论满分抬升: 40G+20C+100 < 240 的模板补一个 goto 任务(2026指南§五 要求>=200)
输出: <out>/stage1/18-XX.xml  <out>/stage2/18-XX.xml
自查: 每题生成后立刻跑 check_cons_init.check(), 有破坏就报错
"""
import os, re, sys, importlib.util, copy

HERE = os.path.dirname(os.path.abspath(__file__))
SK = os.path.join(HERE, "gen_stage1.py")
spec = importlib.util.spec_from_file_location("gen1", SK)
G1 = importlib.util.module_from_spec(spec); spec.loader.exec_module(G1)
sys.path.insert(0, HERE)
import check_cons_init as CCI   # 复用约束初始态检查

SMALL = set("book can remotecontrol bottle cup".split())
CONT = set("closet cupboard refrigerator microwave".split())
BIG = set("human plant couch chair sofa bed table workspace worktable teapoy desk television airconditioner washmachine".split())

# ---- B. 冲突约束改写 (模板序号1起) ----
CONFLICT_FIX = {
    7:  {  # 原: cons_notnot(red book in closet) 与 task puton(red book->sofa) 互斥; 顺带删掉重复的 (:info closed closet)
        "old": "(:cons_notnot (:info (inside X Y) (:cond (sort X book) (color X red) (sort Y closet))))",
        "new_instr": "(:cons_notnot (:info (closed X) (:cond (sort X closet))))",
        "new_nl": "The closet must be closed.",
        "drop": "(:info (closed X) (:cond (sort X closet)))"},
    16: {  # 原: cons_notnot(red book on plant) 与 task puton(red book->worktable) 互斥
        "old": "(:cons_notnot (:info (on X Y) (:cond (sort X book) (color X red) (sort Y plant))))",
        "new_instr": "(:cons_notnot (:info (opened X) (:cond (sort X microwave))))",
        "new_nl": "The microwave must be opened."},
    17: {  # 原: cons_notnot(yellow book in closet) 与 task puton(yellow book->chair) 互斥
        "old": "(:cons_notnot (:info (inside X Y) (:cond (sort X book) (color X yellow) (sort Y closet))))",
        "new_instr": "(:cons_notnot (:info (closed X) (:cond (sort X closet))))",
        "new_nl": "The closet must be closed."},
    20: {  # 原: cons_notnot(white cup on desk) 与 task putin(white cup->microwave) 互斥
        "old": "(:cons_notnot (:info (on X Y) (:cond (sort X cup) (color X white) (sort Y desk))))",
        "new_instr": "(:cons_notnot (:info (closed X) (:cond (sort X cupboard))))",
        "new_nl": "The cupboard must be closed."},
    23: {  # 原: cons_notnot(red can on worktable) 与 task puton(red can->sofa) 互斥
        "old": "(:cons_notnot (:info (on X Y) (:cond (sort X can) (color X red) (sort Y worktable))))",
        "new_instr": "(:cons_notnot (:info (opened X) (:cond (sort X microwave))))",
        "new_nl": "The microwave must be opened."},
}
# 需要补 goto 抬满分的模板 (40G+20C+100 < 240)
NEED_BUMP = [8, 9, 10, 17, 18, 19, 20, 21, 22, 23, 24, 25]

# ---- 阶段2 信息缺失策略 (2026-10-16) ----
# S2_MIS=1 : 方案A —— mis 段放小物体位置(机器人需 AskLoc 发现)
#            但官方 validator 只读 info+err/w、**不读 mis**, 位置在它眼里未知 → ASP 枚举爆炸 → 大面积超时 unvalid
# S2_MIS=0 (默认): 方案B —— mis 段留空, 小物体位置保留在 info(validator 可秒验);
#            第二阶段难度靠 err 的误导位置(w) + ans=on 时 AskLoc 会撒谎 维持
S2_MIS_HIDE = os.environ.get('S2_MIS', '0') == '1'


def parse_cmds(instrs):
    out = []
    for itmpl, ntmpl in instrs:
        try:
            sx = CCI.parse_sexp(itmpl)
        except Exception:
            out.append((itmpl, ntmpl, None)); continue
        cmd = sx[0] if sx and isinstance(sx[0], list) else None
        out.append((itmpl, ntmpl, cmd))
    return out


def find_cond(node):
    """递归找 :cond 节点(普通info指令的:cond是兄弟节点, task/cons的是内层节点)"""
    if isinstance(node, list):
        if node and node[0] == ':cond':
            return CCI.atoms(node[1:])
        for x in node:
            r = find_cond(x)
            if r:
                return r
    return []


def cmd_info(cmd):
    """-> (kind, inner_kind, pred, args, conds)"""
    kind = cmd[0]
    inner = cmd[1] if len(cmd) > 1 and isinstance(cmd[1], list) else None
    if inner is None:
        return (kind, None, None, [], [])
    if inner[0] == ':task':
        pred = inner[1][0] if len(inner) > 1 and isinstance(inner[1], list) else None
        args = inner[1][1:] if len(inner) > 1 and isinstance(inner[1], list) else []
    else:
        pred = inner[1][0] if len(inner) > 1 and isinstance(inner[1], list) else inner[0]
        args = []
        if len(inner) > 1 and isinstance(inner[1], list) and inner[1][0] not in (':cond',):
            args = inner[1][1:]
    conds = find_cond(cmd)
    return (kind, inner[0], pred, args, conds)


def resolve_obj(conds, objs):
    """(sort X a)(color X b) -> {X:[ids], Y:[ids]}"""
    byvar = {}
    for pred, a in conds:
        if len(a) >= 2 and a[0] in ('X', 'Y'):
            byvar.setdefault(a[0], {})[pred] = a[1]
    res = {}
    for var, d in byvar.items():
        hits = []
        for oid, o in objs.items():
            if 'sort' in d and o.sort != d['sort']:
                continue
            if 'color' in d and o.color != d['color']:
                continue
            hits.append(oid)
        res[var] = hits
    return res


def fix_templates():
    """返回 30 个模板(已做 A/B/C 修复)"""
    T = G1.build_templates()
    assert len(T) == 30, len(T)
    out = []
    for i, t in enumerate(T, start=1):
        t = copy.deepcopy(t)
        instrs = list(t["instrs"])
        # ---- C. 补 goto ----
        if i in NEED_BUMP:
            used_big = set()
            for itmpl, ntmpl in instrs:
                for _, _, cmd in parse_cmds([(itmpl, ntmpl)]):
                    if cmd is None:
                        continue
                    k, ik, pred, args, conds = cmd_info(cmd)
                    r = resolve_obj(conds, {})   # 只取 sort 条件
                    for p2, a2 in conds:
                        if p2 == 'sort' and len(a2) >= 2 and a2[1] in BIG:
                            used_big.add(a2[1])
            free = [b for b in t["big"] if b not in used_big]
            if free:
                gb = free[0]
                instrs.append(("(:task (goto X) (:cond (sort X %s)))" % gb, "Go to the %s." % gb))
        # ---- B. 冲突改写 ----
        if i in CONFLICT_FIX:
            fx = CONFLICT_FIX[i]
            if fx.get("drop"):      # 先删冗余的普通info句(避免误删新插入的cons)
                instrs = [(a, b) for a, b in instrs if fx["drop"] not in a]
            hit = False
            for k, (itmpl, ntmpl) in enumerate(instrs):
                if fx["old"] in itmpl:
                    instrs[k] = (fx["new_instr"], fx["new_nl"]); hit = True; break
            if not hit:
                raise SystemExit("模板%d 未找到待改写的约束: %s" % (i, fx["old"]))
        t["instrs"] = instrs
        # ---- A. 约束初始态修复: 计算摆放计划 ----
        plan = plan_placement(t)
        t["_plan"] = plan
        out.append((i, t))
    return out


def plan_placement(t):
    """依据 instr 里各 cons 的要求, 计算 物体摆放/容器状态/手爪盘子"""
    objs, by = G1.build_scene(t["small"], t["cont"], t["big"])
    place = {}                                  # oid -> ('at', loc) | ('inside', cid) | ('plate',) | ('hold',)
    for oid in objs:
        place[oid] = ('at', oid)
    robot = {'at': 5, 'hold': 0, 'plate': 0}
    cstate = {o.sort: o for o in objs.values() if o.ctype == 'container'}
    cont_state = dict(t.get("cont_state") or {})
    for s in cstate:
        cont_state.setdefault(s, "closed")

    def locof(oid):
        p = place.get(oid)
        if p is None:
            return None
        if p[0] == 'at':
            return p[1]
        if p[0] == 'inside':
            return locof(p[1])
        if p[0] in ('plate', 'hold'):
            return robot['at']
        return None

    cmds = parse_cmds(t["instrs"])
    for itmpl, ntmpl, cmd in cmds:
        if cmd is None:
            continue
        kind, ik, pred, args, conds = cmd_info(cmd)
        r = resolve_obj(conds, objs)
        X = r.get('X', [None])[0] if r.get('X') else None
        Y = r.get('Y', [None])[0] if r.get('Y') else None

        def set_true():
            """让该 info 条件在初始状态成立"""
            if pred in ('on', 'near'):
                place[X] = ('at', locof(Y))
            elif pred == 'inside':
                place[X] = ('inside', Y)
            elif pred == 'plate':
                place[X] = ('plate',); robot['plate'] = X
            elif pred == 'opened':
                cont_state[objs[X].sort] = 'opened'
            elif pred == 'closed':
                cont_state[objs[X].sort] = 'closed'
            elif pred == 'hold':
                place[X] = ('hold',); robot['hold'] = X

        def set_false():
            if pred in ('on', 'near'):
                place[X] = ('at', X)
            elif pred == 'inside':
                place[X] = ('at', X)
            elif pred == 'plate':
                place[X] = ('at', X); robot['plate'] = 0
            elif pred == 'opened':
                cont_state[objs[X].sort] = 'closed'
            elif pred == 'closed':
                cont_state[objs[X].sort] = 'opened'
            elif pred == 'hold':
                place[X] = ('at', X); robot['hold'] = 0

        if kind == ':info':
            # ★普通 info 句必须与真实环境一致(2026指南: info内容必须与实际信息一致)
            set_true(); continue
        if kind == ':cons_notnot' and ik == ':info':
            set_true(); continue
        if kind == ':cons_not' and ik == ':info':
            set_false(); continue
        if kind == ':cons_not' and ik == ':task':
            if pred == 'open':
                cont_state[objs[X].sort] = 'closed'
            elif pred == 'close':
                cont_state[objs[X].sort] = 'opened'
            elif pred == 'puton':
                if locof(X) == locof(Y):
                    place[X] = ('at', X)
            elif pred == 'putin':
                if place.get(X, (None,))[0] == 'inside' and place[X][1] == Y:
                    place[X] = ('at', X)
            elif pred == 'pickup':
                if place.get(X, (None,))[0] in ('plate', 'hold'):
                    place[X] = ('at', X); robot['plate'] = 0; robot['hold'] = 0
            elif pred == 'putdown':
                # goal: outagent(X) 必须为假 => X 在手上或盘上
                if place.get(X, (None,))[0] not in ('plate', 'hold'):
                    place[X] = ('plate',); robot['plate'] = X
            elif pred == 'takeout':
                place[X] = ('inside', Y)          # goal: not inside(X,Y) 必须为假
            elif pred == 'goto':
                if robot['at'] == locof(X):
                    robot['at'] = 1
            elif pred == 'give':
                if locof(X) == locof(1):
                    place[X] = ('at', X)
            continue
    return {'place': place, 'robot': robot, 'cont_state': cont_state, 'objs': objs}


def render(t, plan, stage, mis_lines=None, err_r='', err_w=''):
    objs = plan['objs']; place = plan['place']; robot = plan['robot']; cont_state = plan['cont_state']
    mis_set = set()
    for ln in (mis_lines or []):
        m = re.match(r'\((inside|at)\s+(\d+)\s+(\d+)\)', ln.strip())
        if m:
            mis_set.add(m.group(2))
    err_obj = None
    if err_w:
        m = re.match(r'\((inside|at)\s+(\d+)\s+(\d+)\)', err_w.strip())
        if m:
            err_obj = m.group(2)

    lines = ["(hold %d) (plate %d) (at 0 %d)" % (robot['hold'], robot['plate'], robot['at'])]
    for oid in sorted(objs):
        o = objs[oid]
        line = "(sort %d %s) (size %d %s)" % (oid, o.sort, oid, o.size)
        if o.color:
            line += " (color %d %s)" % (oid, o.color)
        # ★2026指南§附录A 字段顺序: sort, size, [color], at/inside, [type], [opened|closed]
        # 容器必须 (at N N) 在 (type N container) 之前, 否则=容器字段描述语法错误(组委会检查器扣500)
        pos = None
        if stage == 1:
            p = place[oid]
            if p[0] == 'at':
                pos = " (at %d %s)" % (oid, p[1])
            elif p[0] == 'inside':
                pos = " (inside %d %s)" % (oid, p[1])
            elif p[0] in ('plate', 'hold'):
                pos = ""                 # 在手/盘上的小物体: 省略 at
        else:
            if o.color is None:
                pos = " (at %d %d)" % (oid, oid)
            else:
                sid = str(oid)
                if sid == err_obj or (S2_MIS_HIDE and sid in mis_set):
                    pos = ""             # 位置被摘走(err 物体=误导; 方案A 下 mis 物体=未知)
                else:
                    p = place[oid]
                    if p[0] == 'at':
                        pos = " (at %d %s)" % (oid, p[1])
                    elif p[0] == 'inside':
                        pos = " (inside %d %s)" % (oid, p[1])
                    elif p[0] in ('plate', 'hold'):
                        pos = ""
        if pos is None:
            pos = " (at %d %d)" % (oid, oid)
        line += pos
        if o.ctype:
            line += " (type %d container)" % oid
            line += " (%s %d)" % (cont_state.get(o.sort, 'closed'), oid)
        lines.append(line)
    info = "\n".join(lines)
    instr_parts = ["    " + a for a, b in t["instrs"]]
    nl_parts = [b for a, b in t["instrs"]]
    # ★2026指南§二.1: 第一阶段 mis/err/ans 均为 off, 第二阶段均为 on
    flags = 'mis="off" err="off" ans="off"' if stage == 1 else 'mis="on" err="on" ans="on"'
    mis_txt = ("\n    ".join(mis_lines)) if mis_lines else ""
    return f'''<?xml version="1.0" encoding="utf-8"?>
<test>
<env {flags}>
    <info>
    {info}
    </info>
    <mis>
    {mis_txt}
    </mis>
    <err>
        <r>{err_r}</r>
        <w>{err_w}</w>
    </err>
    <extra>
    </extra>
</env>
<instr>
(:ins
{chr(10).join(instr_parts)}
)
</instr>
<nl>
{chr(10).join(nl_parts)}
</nl>
</test>
'''


def referenced_small(t, objs):
    """被 cons/info 指令引用的小物体 -> (全部被引用集合, 其中被 :info 引用的子集)
    :info 引用的小物体位置必须与真实环境一致 => 绝不可进 mis/err"""
    ref, info_ref = set(), set()
    for itmpl, ntmpl, cmd in parse_cmds(t["instrs"]):
        if cmd is None:
            continue
        kind, ik, pred, args, conds = cmd_info(cmd)
        if kind in (':cons_not', ':cons_notnot', ':info'):
            r = resolve_obj(conds, objs)
            for v in ('X', 'Y'):
                for oid in r.get(v, []):
                    if objs[oid].color is not None:
                        ref.add(oid)
                        if kind == ':info':
                            info_ref.add(oid)
    return ref, info_ref


def stage2_placement(t, plan):
    """给 mis/err 选位置, 并验证所有约束在 真状态 与 可见状态(info+w) 都成立"""
    objs = plan['objs']
    ref, info_ref = referenced_small(t, objs)
    # mis 候选 = 未被 cons/info 引用的自由小物体
    cand_small = [oid for oid in sorted(objs) if objs[oid].color is not None and oid not in ref]
    if not cand_small:
        cand_small = [oid for oid in sorted(objs) if objs[oid].color is not None and oid not in info_ref]
    # err 候选 = mis 候选 + (被 cons 引用但未被 :info 引用的小物体);
    # 平台49/49题 err 段均非空且 mis∩err=∅, 故自由小物体不足2个时借 cons 引用的小物体当 err 对象:
    # err 的 r 写"真实位置"(评分环境=info+mis+r 依旧正确), r 是否满足约束仍由 CCI.check 逐候选验证.
    err_pool = list(cand_small)
    if len(err_pool) < 2:
        err_pool = err_pool + [oid for oid in sorted(objs) if objs[oid].color is not None
                               and oid not in err_pool and oid not in info_ref]
    mis_pick = cand_small[0] if cand_small else None
    err_pick = next((o for o in err_pool if o != mis_pick), None) if len(err_pool) > 1 else None
    pool = sorted(set(cand_small) | set(err_pool))
    # ★ 被约束保护的容器: cons_notnot(closed X) / cons_not(:task (open X))
    #   若 w 把物体放进这类容器, 机器人视角下"必须开门取出"与约束冲突 = 死局
    #   (2026-10-16 实锤: 18-20 的 w 放进 cons_notnot 保护的 cupboard → validator 90s+ 解不出)
    protected = set()
    for _i, _n, _cmd in parse_cmds(t["instrs"]):
        if _cmd is None:
            continue
        _k, _ik, _p, _a, _cds = cmd_info(_cmd)
        if _k == ':cons_notnot' and _p == 'closed':
            protected |= set(resolve_obj(_cds, objs).get('X', []))
        if _k == ':cons_not' and _ik == ':task' and _p == 'open':
            protected |= set(resolve_obj(_cds, objs).get('X', []))
    cands = []
    for c in [oid for oid in sorted(objs) if objs[oid].ctype == 'container']:
        if c in protected:
            continue          # w 不可放进受保护容器(否则机器人视角死局)
        for s in pool:
            cands.append(('inside', s, c))
    for b in [oid for oid in sorted(objs) if objs[oid].color is None and objs[oid].sort in BIG and objs[oid].sort != 'human']:
        for s in pool:
            cands.append(('at', s, b))

    def render_try(mis, err_r, err_w):
        ml = ['(%s %d %d)' % mis] if mis else []
        return render(t, plan, 2, mis_lines=ml, err_r=('(%s %d %d)' % err_r) if err_r else '',
                      err_w=('(%s %d %d)' % err_w) if err_w else '')

    def ok(xml):
        p = '/tmp/gen_v2/_try.xml'
        open(p, 'w', encoding='utf-8').write(xml)
        try:
            return len(CCI.check(p)) == 0
        except Exception:
            return False

    best = None
    # mis: 第1个小物体(方案B 下不设 mis, 位置保留在 info); err: 第2个
    mis_opts = ([c for c in cands if mis_pick is not None and c[1] == mis_pick] if S2_MIS_HIDE else [None])
    for mis in mis_opts:
        for r in cands:
            if err_pick is None or r[1] != err_pick:
                continue
            for w in cands:
                if w[1] != r[1]:
                    continue
                if (w[0], w[2]) == (r[0], r[2]):
                    continue
                xml = render_try(mis, r, w)
                if ok(xml):
                    best = xml
                    break
            if best:
                break
        if best:
            break
    if best is None:
        # 退化: 只设 mis(方案B 下 mis=None), 不设 err
        fb = ([None] if not S2_MIS_HIDE
              else [c for c in cands if mis_pick is not None and c[1] == mis_pick] or [None])
        for mis in fb:
            xml = render_try(mis, None, None)
            if ok(xml):
                best = xml
                break
    if best is None:
        best = render(t, plan, 2)
        print("  [警告] 未能找到满足约束的 mis/err 摆放, 已退化输出")
    return best


def main(outdir):
    os.makedirs(outdir + '/stage1', exist_ok=True)
    os.makedirs(outdir + '/stage2', exist_ok=True)
    os.makedirs('/tmp/gen_v2', exist_ok=True)
    bad = []
    for i, t in fix_templates():
        plan = t['_plan']
        s1 = render(t, plan, 1)
        p1 = '%s/stage1/18-%02d.xml' % (outdir, i)
        open(p1, 'w', encoding='utf-8').write(s1)
        iss = CCI.check(p1)
        if iss:
            bad.append((i, 'stage1', iss))
        s2 = stage2_placement(t, plan)
        p2 = '%s/stage2/18-%02d.xml' % (outdir, i)
        open(p2, 'w', encoding='utf-8').write(s2)
        iss = CCI.check(p2)
        if iss:
            bad.append((i, 'stage2', iss))
    open('%s/stage1/test.list' % outdir, 'w').write("\n".join("18-%02d.xml" % i for i in range(1, 31)) + "\n")
    open('%s/stage2/test.list' % outdir, 'w').write("\n".join("18-%02d.xml" % i for i in range(1, 31)) + "\n")
    print("生成完毕 -> %s" % outdir)
    if bad:
        print("!! 仍有约束初始态问题的题:")
        for i, st, iss in bad:
            print("   18-%02d %s: %s" % (i, st, iss[:3]))
    else:
        print("✓ 60题约束初始态全部自检通过")


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '/tmp/tests_v2')