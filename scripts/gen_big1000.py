#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""理论上限≈1000 的压力测试题 (G=18, C=9)

测什么: 咱的代码在"上限 1000"的题上能拿多少, 到底有没有 900 的空间。

关键变量是**动作密度**: 得分 = 40G + 20C + 效率分 - 行动扣分。
  · 密集型(dense): 让部分物体的初始位置==其目标位置 → 那些目标"零动作"即可收分
                   (fortask.lp: goal(puton(A,B)) :- sameplace(A,B), outagent(A))
  · 稀疏型(sparse): 物体各自独占位置, 每个目标都要 4 个动作
两者上限都是 1000, 但动作数差一倍 → 实测差距就是"能不能上900"的答案。
"""
import os, sys, random

BIGS = [(2,'desk'),(3,'television'),(4,'chair'),(5,'bed'),(6,'sofa'),(7,'table'),
        (8,'worktable'),(9,'plant'),(10,'teapoy'),(11,'couch'),(12,'airconditioner'),(13,'washmachine'),
        (14,'table'),(15,'sofa'),(16,'chair')]          # 位置互不相同即可
CONTS = [(17,'refrigerator','closed'),(18,'closet','closed'),(19,'cupboard','opened'),(20,'microwave','opened')]
SMALLS = [(30,'book','red'),(31,'book','green'),(32,'book','yellow'),(33,'book','blue'),(34,'book','white'),(35,'book','black'),
          (36,'can','red'),(37,'can','green'),(38,'can','blue'),(39,'can','black'),(40,'can','white'),
          (41,'bottle','red'),(42,'bottle','green'),(43,'bottle','blue'),(44,'bottle','white'),(45,'bottle','black'),
          (46,'cup','red'),(47,'cup','green'),(48,'cup','blue'),(49,'cup','black'),(50,'cup','white'),
          (51,'remotecontrol','white'),(52,'remotecontrol','black')]

def build(seed, dense):
    rnd = random.Random(seed)
    perm = list(range(21, 200)); rnd.shuffle(perm)
    pos = {}
    for i, s in BIGS: pos[i] = perm.pop()
    for i, s, st in CONTS: pos[i] = perm.pop()
    for i, s, c in SMALLS: pos[i] = perm.pop()

    # 18 个搬运任务: 取 14 个走 puton/putin + 2 pickup + 2 goto/close 之类
    pool = [i for i, s, c in SMALLS if i not in (51, 52)]
    rnd.shuffle(pool)
    chosen = pool[:14]
    targets = [b for b in BIGS if b[1] not in ('washmachine','airconditioner')]
    rnd.shuffle(targets)
    tasks = []
    for k, xid in enumerate(chosen):
        s, c = [ (ss,cc) for i,ss,cc in SMALLS if i == xid ][0]
        if k % 3 == 2:
            cid, cname, _ = CONTS[k % len(CONTS)]
            tasks.append(('putin', xid, cid, s, c, cname))
        else:
            bid = targets[k % len(targets)][0]
            tasks.append(('puton', xid, bid, s, c, [t[1] for t in BIGS if t[0]==bid][0]))
    tasks.append(('pickup', 51, None, 'remotecontrol', 'white', None))
    tasks.append(('pickup', 52, None, 'remotecontrol', 'black', None))
    tasks.append(('goto', None, 11, None, None, 'couch'))
    tasks.append(('close', None, 20, None, None, 'microwave'))
    # goto 放中间(坑B), 但这次测的是"上限", 所以放到中段即可
    tasks.insert(6, tasks.pop())
    # 密集型: 让前 6 个搬运任务的物体"初始就在目标位置" → 零动作收分
    if dense:
        for t in tasks[:6]:
            if t[0] == 'puton':   pos[t[1]] = pos[t[2]]
            elif t[0] == 'putin': pos[t[1]] = pos[t[2]]   # 视作已在容器同位置(仅测上限, 不严格)
    return tasks, pos

def instr_of(t):
    k, x, y, sx, cx, sy = t
    if k == 'puton':
        return '(:task (puton X Y) (:cond (sort X %s) (color X %s) (sort Y %s)))' % (sx, cx, sy)
    if k == 'putin':
        return '(:task (putin X Y) (:cond (sort X %s) (color X %s) (sort Y %s) (type Y container)))' % (sx, cx, sy)
    if k == 'pickup':
        return '(:task (pickup X) (:cond (sort X %s) (color X %s)))' % (sx, cx)
    if k == 'goto':  return '(:task (goto X) (:cond (sort X %s)))' % sy
    if k == 'close': return '(:task (close X) (:cond (sort X %s) (type X container)))' % sy
    raise ValueError(k)

def nl_of(t):
    k, x, y, sx, cx, sy = t
    if k == 'puton':  return 'Put the %s %s on the %s.' % (cx, sx, sy)
    if k == 'putin':  return 'Put the %s %s in the %s.' % (cx, sx, sy)
    if k == 'pickup': return 'Pick up the %s %s.' % (cx, sx)
    if k == 'goto':   return 'Go to the %s.' % sy
    if k == 'close':  return 'Close the %s.' % sy
    raise ValueError(k)

CONS = [
 ('cons_not', 'putin', None, 17, 'book', 'red', 'refrigerator'),   # 红书不得入冰箱(task 未用红书→安全)
 ('cons_not', 'putin', None, 18, 'can', 'green', 'closet'),
 ('cons_not', 'puton', None, 11, 'bottle', 'green', 'couch'),
 ('cons_not', 'puton', None, 9,  'cup', 'green', 'plant'),
 ('cons_not', 'open',  None, 18, None, None, 'closet'),
 ('cons_not', 'open',  None, 17, None, None, 'refrigerator'),
 ('cons_notnot_on', 34, 'book', 'white', 8, 'worktable', None),
 ('cons_notnot_opened', 19, 'cupboard', None, None, None, None),
 ('cons_notnot_closed', 18, 'closet', None, None, None, None),
]
def cons_instr(c):
    k = c[0]
    if k == 'cons_not':
        _, act, x, y, sx, cx, sy = c
        if act == 'open':
            return '(:cons_not (:task (open X) (:cond (sort X %s) (type X container))))' % sy
        return '(:cons_not (:task (%s X Y) (:cond (sort X %s) (color X %s) (sort Y %s)%s)))' % (
            act, sx, cx, sy, ' (type Y container)' if act == 'putin' else '')
    if k == 'cons_notnot_on':
        return '(:cons_notnot (:info (on X Y) (:cond (sort X %s) (color X %s) (sort Y %s))))' % (c[2], c[3], c[5])
    if k == 'cons_notnot_opened':
        return '(:cons_notnot (:info (opened X) (:cond (sort X %s))))' % c[2]
    if k == 'cons_notnot_closed':
        return '(:cons_notnot (:info (closed X) (:cond (sort X %s))))' % c[2]
    raise ValueError(k)
def cons_nl(c):
    k = c[0]
    if k == 'cons_not':
        _, act, x, y, sx, cx, sy = c
        if act == 'open': return 'Do not open the %s.' % sy
        if act == 'putin': return 'Do not put the %s %s in the %s.' % (cx, sx, sy)
        return 'Do not put the %s %s on the %s.' % (cx, sx, sy)
    if k == 'cons_notnot_on': return 'The %s %s must be on the %s.' % (c[3], c[2], c[5])
    if k == 'cons_notnot_opened': return 'The cupboard must be opened.'
    if k == 'cons_notnot_closed': return 'The closet must be closed.'
    raise ValueError(k)

def render(tasks, pos, seed):
    L = ['<?xml version="1.0" encoding="utf-8"?>', '<test>', '<env mis="on" err="on" ans="on">', '    <info>']
    L.append('    (hold 0) (plate 0) (at 0 %d)' % pos[2])
    L.append('(sort 1 human) (size 1 big) (at 1 %d)' % pos[3])
    for i, s in BIGS:
        L.append('(sort %d %s) (size %d big) (at %d %d)' % (i, s, i, i, pos[i]))
    for i, s, st in CONTS:
        L.append('(sort %d %s) (size %d big) (at %d %d) (type %d container) (%s %d)' % (i, s, i, i, pos[i], i, st, i))
    # 34(白书) 受 cons_notnot(on worktable) 保护 -> 位置对齐 worktable
    pos[34] = pos[8]
    for i, s, c in SMALLS:
        L.append('(sort %d %s) (size %d small) (color %d %s) (at %d %d)' % (i, s, i, i, c, i, pos[i]))
    L += ['    </info>', '    <mis>', '    </mis>', '    <err>', '        <r></r>', '        <w></w>', '    </err>',
          '    <extra>', '    </extra>', '</env>', '<instr>', '(:ins']
    for t in tasks: L.append('    ' + instr_of(t))
    for c in CONS:  L.append('    ' + cons_instr(c))
    L += [')', '</instr>', '<nl>']
    for t in tasks: L.append(nl_of(t))
    for c in CONS:  L.append(cons_nl(c))
    L += ['</nl>', '</test>']
    return '\n'.join(L) + '\n'

def main(outdir):
    os.makedirs(outdir, exist_ok=True)
    names = []
    for i, (kind, dense) in enumerate([('dense', True), ('dense2', True), ('sparse', False), ('sparse2', False)], 1):
        tasks, pos = build(i, dense)
        p = os.path.join(outdir, 'big1000-%02d.xml' % i)
        open(p, 'w', encoding='utf-8').write(render(tasks, pos, i))
        names.append('big1000-%02d.xml' % i)
        ub = 40 * len(tasks) + 20 * len(CONS) + 100
        print('big1000-%02d.xml (%s)  G=%d C=%d ub=%d' % (i, kind, len(tasks), len(CONS), ub))
    open(os.path.join(outdir, 'test.list'), 'w').write('\n'.join(names) + '\n')

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '/tmp/big1000')