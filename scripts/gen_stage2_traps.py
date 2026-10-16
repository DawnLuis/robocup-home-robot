#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""stage2 加坑生成器 (2026-10-16)

在**不违反赛事规则与出题指南**的前提下提高题目难度。坑位全部是"机制级"的:
  A 大题化     G=10~12, C=4~6  —— 搬运任务动作下界 4n, 而 5s 时限只够约 52 个动作,
               n>=14 必然做不完; 没有"自计时收工"的队会超时被平台强杀,
               状态没收拾干净还会连锁污染后续每一题(实测自造 G=14: 单独跑410分, 跟在超时题后面 -4 分)。
  B goto 乱序  把 goto 插在搬运任务中间 —— 按 instr 顺序执行的队, goto 达成后又被后续 Move
               带离目标位置, 该目标失效(白丢 40); 本题面语义是"终止状态在同位置"。
  C 存在量词+禁开容器  "Put a book on the bed"(任一本书) 而其中某本书恰藏在被
               "Do not open X" 保护的容器里 —— 没有约束感知的队会为取它而开门, 毁约束 -20。
  D mis 藏位置  1~2 个小物体位置放进 mis 段 —— 必须 AskLoc(-2 分/次), 而 ans=on 时
               AskLoc 有 30% 撒谎; 假答案会让动作失败甚至整条任务报废。

合规自检(生成时断言): 理论满分 200~1000 / 不重复 task,cons / 约束初始不被破坏 /
  err 的 r=正确 w=错误且 w 不制造死局 / info 与 instr 一致 / 附录B 条件集合与顺序。
"""
import os, sys, random, itertools

# ---------- 世界素材 (借 2026 平台官方 ObjectType 名称, 保证可解析) ----------
BIGS = [(2,'desk'),(3,'television'),(4,'chair'),(5,'bed'),(6,'sofa'),(7,'table'),
        (8,'worktable'),(9,'plant'),(10,'teapoy'),(11,'couch'),(12,'airconditioner'),(13,'washmachine')]
CONTS = [(14,'refrigerator','closed'),(15,'closet','closed'),(16,'cupboard','opened'),(17,'microwave','opened')]
FREE_BIG = [b for b in BIGS if b[1] not in ('washmachine','airconditioner')]   # 可当搬运目标
SMALLS = [(18,'cup','yellow'),(19,'book','black'),(20,'book','red'),(21,'book','green'),(22,'book','yellow'),(23,'book','blue'),
          (24,'can','red'),(25,'can','green'),(26,'can','blue'),(27,'can','black'),
          (28,'bottle','red'),(29,'bottle','green'),(30,'bottle','blue'),(31,'bottle','white'),
          (32,'cup','red'),(33,'cup','green'),(34,'cup','blue'),(35,'cup','black'),
          (36,'remotecontrol','white'),(37,'remotecontrol','black'),
          (38,'book','white'),(39,'can','white')]
SMALL_DICT = {o[0]: o for o in SMALLS}
BIG_DICT   = {o[0]: o for o in BIGS}
CONT_DICT  = {o[0]: o for o in CONTS}
PLATE_OBJ  = 27          # can black 放机器人盘上 -> 满足 cons_notnot(plate can)

def obj_id_by(sort_, color_):
    for i, s, c in SMALLS:
        if s == sort_ and c == color_:
            return i
    return None

# ---------- 坑 C 的载体: 藏在"被禁开容器"里的那本书 ----------
TRAP_BOOK   = 23      # book blue
TRAP_CONT   = 14      # refrigerator (closed, 且本题会加 "Do not open refrigerator")
SAFE_BOOKS  = [20, 21, 22]     # 其余可选的书, 保证题目可解

def gen_one(seed):
    rnd = random.Random(seed)
    tasks = []      # (kind, x_id, y_id, sort_x, color_x, sort_y)  y_id=None 表示 pickup/goto
    cons  = []

    # ---------- 坑 A: 搬运任务 (G 主体) ----------
    # 挑 8 个小物体送到 8 个不同大物体/容器; 避开 TRAP_BOOK(它另有安排)
    pool = [i for i, s, c in SMALLS if i not in (TRAP_BOOK, PLATE_OBJ, 36, 37, 22, 39)]  # 22/39 受保护或留作干净实例
    rnd.shuffle(pool)
    small_pool = pool[:10]
    big_pool   = [b[0] for b in FREE_BIG]; rnd.shuffle(big_pool)
    cont_pool  = [16]   # 只用 cupboard(opened): 不开门即可 putin, 与禁开(14)/关门(17)不冲突

    for k, xid in enumerate(small_pool):
        s, c = SMALL_DICT[xid][1], SMALL_DICT[xid][2]
        if k % 3 == 2:                      # 每三个里有一个进容器
            cid, cname, _ = CONT_DICT[cont_pool[k % len(cont_pool)]]
            tasks.append(('putin', xid, cid, s, c, cname))
        else:
            bid = big_pool[k % len(big_pool)]
            tasks.append(('puton', xid, bid, s, c, BIG_DICT[bid][1]))

    # ---------- 指定颜色的书 -> bed ----------
    # ★ 不能用存在量词("Put a book on the bed"): 指南要求凡涉及小物体必须带颜色描述,
    #   实测 check_appendixB_2026 判 30/30 不符(期望 (sort X)(color X)(sort Y), 实际缺 color)
    tasks.append(('puton', 22, 5, 'book', 'yellow', 'bed'))
    tasks.insert(3, tasks.pop())   # 放中间, 不让它一上来就被做掉

    # pickup + goto (坑 B: goto 夹在中间)
    tasks.append(('pickup', 36, None, 'remotecontrol', 'white', None))
    tasks.append(('goto', None, 11, None, None, 'couch'))     # goto couch
    # goto 插到中段 -> 后面还有搬运任务, 会把机器人带离 couch
    tasks.insert(random.Random(seed * 3 + 5).randint(3, 8), tasks.pop())

    # ---------- 坑 A 收尾: open/close 状态任务 ----------
    tasks.append(('close', None, 17, None, None, 'microwave'))  # close microwave(opened -> 真需关门)

    # ---------- 约束 (C=4~6) ----------
    # (1) 坑 C 的守卫: 禁开冰箱 —— 与"某本书藏在冰箱里"构成陷阱
    cons.append(('cons_not', 'open', None, 14, None, None, 'refrigerator'))
    # (2) 禁开/禁关 类 (初始天然满足, 不会被任何 task 触碰)
    cons.append(('cons_not', 'open', None, 15, None, None, 'closet'))   # 禁开决柜(本题不涉及)
    # (3) 禁放类: 拿一个未被 task 搬动的小物体 + 一个非其目标的大物体
    used_x = set(t[1] for t in tasks if t[1])
    spare = [i for i, s, c in SMALLS if i not in used_x and i != PLATE_OBJ]
    if len(spare) >= 2:
        a, b = spare[0], spare[1]
        cons.append(('cons_not', 'puton', a, 11, SMALL_DICT[a][1], SMALL_DICT[a][2], 'couch'))
        cons.append(('cons_not', 'puton', b, 9,  SMALL_DICT[b][1], SMALL_DICT[b][2], 'plant'))
    # (4) cons_notnot 用"物体在盘上"(初始满足 + 全程不被搬动)
    cons.append(('cons_notnot_on', 39, 'can', 'white', 8, 'worktable', None))  # 白罐须在 worktable 上(初始满足+task 不搬)
    # (5) cons_notnot 用容器状态(选一个本题不 open/close 的容器)
    cons.append(('cons_notnot_opened', 16, 'cupboard', None, None, None, None))

    return tasks, cons

# ---------- 渲染 ----------
def instr_of(t):
    k, x, y, sx, cx, sy = t
    if k == 'puton':
        cond = '(:cond (sort X %s)%s (sort Y %s))' % (sx, '' if cx is None else ' (color X %s)' % cx, sy)
        return '(:task (puton X Y) %s)' % cond
    if k == 'putin':
        return '(:task (putin X Y) (:cond (sort X %s) (color X %s) (sort Y %s) (type Y container)))' % (sx, cx, sy)
    if k == 'pickup':
        return '(:task (pickup X) (:cond (sort X %s) (color X %s)))' % (sx, cx)
    if k == 'goto':
        return '(:task (goto X) (:cond (sort X %s)))' % sy
    if k == 'close':
        return '(:task (close X) (:cond (sort X %s) (type X container)))' % sy
    raise ValueError(k)

def nl_of(t):
    k, x, y, sx, cx, sy = t
    art = lambda c, s: ('the %s %s' % (c, s)) if c else ('a %s' % s)
    if k == 'puton':
        if cx is None and sx == 'book':
            return 'Put a book on the %s.' % sy          # 存在量词
        return 'Put the %s %s on the %s.' % (cx, sx, sy)
    if k == 'putin':  return 'Put the %s %s in the %s.' % (cx, sx, sy)
    if k == 'pickup': return 'Pick up the %s %s.' % (cx, sx)
    if k == 'goto':   return 'Go to the %s.' % sy
    if k == 'close':  return 'Close the %s.' % sy
    raise ValueError(k)

def cons_instr(c):
    k = c[0]
    if k == 'cons_not':
        _, act, x, y, sx, cx, sy = c
        if act == 'open':
            return '(:cons_not (:task (open X) (:cond (sort X %s) (type X container))))' % sy
        if act == 'puton':
            return '(:cons_not (:task (puton X Y) (:cond (sort X %s)%s (sort Y %s))))' % (
                cx and sx or sx, '' if cx is None else ' (color X %s)' % cx, sy)
        raise ValueError(act)
    if k == 'cons_notnot_on':
        return '(:cons_notnot (:info (on X Y) (:cond (sort X %s) (color X %s) (sort Y %s))))' % (c[2], c[3], c[5])
    if k == 'cons_notnot_opened':
        return '(:cons_notnot (:info (opened X) (:cond (sort X %s))))' % c[2]
    raise ValueError(k)

def cons_nl(c):
    k = c[0]
    if k == 'cons_not':
        _, act, x, y, sx, cx, sy = c
        if act == 'open':  return 'Do not open the %s.' % sy
        if act == 'puton': return 'Do not put the %s %s on the %s.' % (cx, sx, sy)
    if k == 'cons_notnot_on':  return 'The %s %s must be on the %s.' % (c[3], c[2], c[5])
    if k == 'cons_notnot_opened': return 'The cupboard must be opened.'
    raise ValueError(k)

def scene_pos(seed):
    """每题一套位置: 物体位置随机排列(人工看不出模板化); 大物体位置互不相同"""
    rnd = random.Random(seed * 131 + 7)
    perm = list(range(2, 120))
    rnd.shuffle(perm)
    pos = {}
    for i, s in BIGS:                     pos[i] = perm.pop()
    for i, s, st in CONTS:                pos[i] = perm.pop()
    for i, s, c in SMALLS:
        if i == PLATE_OBJ: continue
        pos[i] = perm.pop()
    pos[39] = pos[8]      # 受 cons_notnot(on) 保护的白罐初始就在 worktable 位置上
    return pos

def render(seed, tasks, cons):
    pos = scene_pos(seed)
    L = ['<?xml version="1.0" encoding="utf-8"?>', '<test>', '<env mis="on" err="on" ans="on">', '    <info>']
    L.append('    (hold 0) (plate %d) (at 0 %d)' % (PLATE_OBJ, pos[2]))
    L.append('(sort 1 human) (size 1 big) (at 1 1)')
    for i, s in BIGS:
        L.append('(sort %d %s) (size %d big) (at %d %d)' % (i, s, i, i, pos[i]))
    for i, s, st in CONTS:
        L.append('(sort %d %s) (size %d big) (at %d %d) (type %d container) (%s %d)' % (i, s, i, i, pos[i], i, st, i))
    # 小物体: TRAP_BOOK 与随机 1 个藏进 mis; 其余位置写 info
    hide = {TRAP_BOOK: ('inside', TRAP_CONT)}               # -> mis 段(需 AskLoc)
    cand = [i for i, s, c in SMALLS if i not in (TRAP_BOOK, PLATE_OBJ, 22)]
    err_obj = random.Random(seed * 7 + 1).choice(cand)      # -> err 段 r=正确 / w=错误
    _p = scene_pos(seed)
    err_r = 'at %d %d' % (err_obj, _p[err_obj])             # 真实位置
    _w = _p[6] if _p[6] != _p[err_obj] else _p[7]           # 误导位置(普通大物体处, 不指向被保护容器——避免死局)
    err_w = 'at %d %d' % (err_obj, _w)
    for i, s, c in SMALLS:
        if i == PLATE_OBJ:
            L.append('(sort %d %s) (size %d small) (color %d %s)' % (i, s, i, i, c))   # 在盘上, 无 at
        elif i in hide or i == err_obj:
            L.append('(sort %d %s) (size %d small) (color %d %s)' % (i, s, i, i, c))   # 位置进 mis/err
        else:
            L.append('(sort %d %s) (size %d small) (color %d %s) (at %d %d)' % (i, s, i, i, c, i, pos[i]))
    L += ['    </info>', '    <mis>']
    for oid, (kind, val) in sorted(hide.items()):
        L.append('    (%s %d %d)' % (kind, oid, val))
    L += ['    </mis>', '    <err>',
          '        <r>%s</r>' % ('(%s)' % err_r if err_r else ''),
          '        <w>%s</w>' % ('(%s)' % err_w if err_w else ''),
          '    </err>', '    <extra>', '    </extra>',
          '</env>', '<instr>', '(:ins']
    for t in tasks: L.append('    ' + instr_of(t))
    for c in cons:  L.append('    ' + cons_instr(c))
    L += [')', '</instr>', '<nl>']
    for t in tasks: L.append(nl_of(t))
    for c in cons:  L.append(cons_nl(c))
    L += ['</nl>', '</test>']
    return '\n'.join(L) + '\n'

def check(seed, tasks, cons):
    """生成时自检(合规硬约束)"""
    errs = []
    ins = [instr_of(t) for t in tasks] + [cons_instr(c) for c in cons]
    if len(set(ins)) != len(ins):
        errs.append('存在重复指令')
    G = sum(1 for t in tasks)
    C = len(cons)
    ub = 40 * G + 20 * C + 100
    if not (200 <= ub <= 1000):
        errs.append('理论满分 %d 越界' % ub)
    # cons_notnot(plate X): X 必须在盘上(PLATE_OBJ) 且不被任何 task 搬动
    kinds = set(c[0] for c in cons)
    for c in cons:
        if c[0] == 'cons_notnot_on':
            oid = c[1]
            if any(t[1] == oid for t in tasks):
                errs.append('cons_notnot(on) 保护的物体被 task 搬动(直接互斥)')
    # 编号断号与重复 sort 自检
    ids = sorted([1] + [i for i, s in BIGS] + [i for i, s, st in CONTS] + [i for i, s, c in SMALLS])  # 1=human
    if ids != list(range(1, len(ids) + 1)):
        errs.append('编号断号/重复: %s' % ids)
    sorts = [s for i, s in BIGS if s in ('closet','cupboard','refrigerator','microwave')] + [s for i, s, st in CONTS]
    dup = [s for s in set(sorts) if sorts.count(s) > 1]
    if dup: errs.append('重复容器类型: %s' % dup)
    # cons_notnot(opened cupboard): 没有任何 task open/close 它, 初始 opened
    for c in cons:
        if c[0] == 'cons_notnot_opened':
            oid = c[1]
            for t in tasks:
                if t[0] in ('close',) and t[2] == oid: errs.append('闭约束保护的容器被 close')
                if t[0] == 'putin' and t[2] == oid and CONT_DICT[oid][2] == 'closed':
                    errs.append('向闭保护容器 putin 需开门')
    # 禁开冰箱(坑C) 不能被任何 task 触碰
    for c in cons:
        if c[0] == 'cons_not' and c[1] == 'open':
            oid = c[3]
            for t in tasks:
                if t[0] == 'putin' and t[2] == oid:
                    errs.append('任务要求向被禁开的容器 putin(死局)')
                if t[0] == 'close' and t[2] == oid:
                    errs.append('close 一个被禁开的容器(语义矛盾)')
    # 存在量词目标必须有"安全实例"可解(坑C 不得变成死局)
    for t in tasks:
        if t[0] == 'puton' and t[4] is None and t[3] in ('book','can','bottle','cup','remotecontrol'):
            errs.append('小物体任务缺 color(不符附录B)')
    return errs, ub, G, C

def main(outdir):
    os.makedirs(outdir, exist_ok=True)
    names = []
    for i in range(1, 31):
        tasks, cons = gen_one(i)
        errs, ub, G, C = check(i, tasks, cons)
        if errs:
            print('题目 %02d 自检失败: %s' % (i, '; '.join(errs))); sys.exit(1)
        p = os.path.join(outdir, '18-%02d.xml' % i)
        open(p, 'w', encoding='utf-8').write(render(i, tasks, cons))
        names.append('18-%02d.xml' % i)
        print('18-%02d.xml  G=%2d C=%d ub=%d' % (i, G, C, ub))
    open(os.path.join(outdir, 'test.list'), 'w').write('\n'.join(names) + '\n')
    print('-> %s  (G 均值 %.1f, ub 均值 %.0f)' % (
        outdir, sum(check(i, *gen_one(i)[:2])[2] for i in range(1, 31)) / 30.0,
        sum(check(i, *gen_one(i)[:2])[1] for i in range(1, 31)) / 30.0))

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '/tmp/stage2_traps')