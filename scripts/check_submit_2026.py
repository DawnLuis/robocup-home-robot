#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2026 stage1 提交前终检 (在 check_rules_2026.py 之后的第二道关)

覆盖 check_rules_2026 未做的项:
  1. 理论满分核算(指南§五): 40G+20C+100 - 行动扣分 >= 200  (用官方validator的ASP答案集当参考方案)
  2. NL 与 instr 逐句一一对应(指南§四.2 / 附录C 句型关键词)
  3. info 按物体编号升序排列(指南§二.1)
  4. sort 后各字段的物体 id 与 sort 一致(指南§二.2注4)
  5. info 中小物体必须有 at 或 inside, 除非在 robot 的 hold/plate(指南§二.2注2+3)
  6. 观察项: robot 所在位置是否与其他大物体重合(指南§二.2注6 的口径确认)

用法:
  python3 check_submit_2026.py <题目目录> [--testlog /tmp/val2026_new_s1/testlog.txt]
"""
import re, sys, os, glob, collections, argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_rules_2026 as CR

# ---- 附录C 句型关键词(指南§四.3: 单词必须出自规则词汇表) ----
NL_PAT = {
    ('task', 'give'):      [(r'\bgive\b', 'give')],
    ('task', 'puton'):     [(r'\bput\b', 'put'), (r'\b(on|near|next to)\b', 'on/near/next to')],
    ('task', 'goto'):      [(r'\bgo to\b', 'go to')],
    ('task', 'putdown'):   [(r'\bput\b', 'put'), (r'\bdown\b', 'down')],
    ('task', 'pickup'):    [(r'\bpick\b', 'pick'), (r'\bup\b', 'up')],
    ('task', 'open'):      [(r'\bopen\b', 'open')],
    ('task', 'close'):     [(r'\bclose\b', 'close')],
    ('task', 'putin'):     [(r'\bput\b', 'put'), (r'\bin\b', 'in')],
    ('task', 'takeout'):   [(r'\btake\b', 'take'), (r'\bout\b', 'out')],
    ('info', 'on'):        [(r'\b(on|near|next to)\b', 'on/near')],
    ('info', 'near'):      [(r'\b(on|near|next to)\b', 'on/near')],
    ('info', 'plate'):     [(r'\bon the plate\b', 'on the plate')],
    ('info', 'inside'):    [(r'\bin\b', 'in')],
    ('info', 'opened'):    [(r'is opened\b', 'is opened')],
    ('info', 'closed'):    [(r'is closed\b', 'is closed')],
    ('cons_not', 'task'):  [(r'\bDo not\b', 'Do not')],
    ('cons_not', 'info'):  [(r'\bmust not be\b', 'must not be')],
    ('cons_notnot', 'info'): [(r'\bmust be\b', 'must be')],
}

COST = {'move': 4, 'pickup': 2, 'putdown': 2, 'open': 2, 'close': 2, 'putin': 2,
        'takeout': 2, 'toplate': 2, 'fromplate': 2, 'give': 2, 'askloc': 2, 'sense': 1}


def cmd_kind(c):
    """返回 (外层关键词, 内层谓词): task/info 取内层谓词; cons 剥掉 :task/:info 一层"""
    if c[0].startswith(':cons'):
        outer = c[0][1:]
        body = c[1] if len(c) > 1 and isinstance(c[1], list) else None
        if not body:
            return outer, None
        inner = body[0]
        if inner in (':task', ':info') and len(body) > 1 and isinstance(body[1], list):
            inner = body[1][0]
        return outer, inner
    body = c[1] if len(c) > 1 and isinstance(c[1], list) else None
    return c[0][1:], (body[0] if body and isinstance(body[0], str) else None)


def cmd_cond(c):
    body = c[1] if c[0].startswith(':cons') and len(c) > 1 and isinstance(c[1], list) else c
    for x in body[1:]:
        if isinstance(x, list) and x and x[0] == ':cond':
            return CR.atoms(x[1:])
    return []


def parse_answerset(testlog):
    txt = open(testlog, encoding='utf-8', errors='replace').read()
    out = []
    for m in re.finditer(r'Execution (success|failed)!\s*Computed answer set is ([^\n]*)', txt):
        ok, body = m.group(1) == 'success', m.group(2)
        acts = re.findall(r'occurs\((\w+)\(', body)
        out.append((ok, acts))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--testlog', default=None)
    a = ap.parse_args()

    files = []
    for d in a.dirs:
        files += sorted(glob.glob(os.path.join(d, '*.xml')))
    answers = parse_answerset(a.testlog) if a.testlog and os.path.exists(a.testlog) else []

    print("=== 提交前终检: %d 道题 ===" % len(files))
    bad = 0
    rows = []
    for idx, f in enumerate(files):
        name = os.path.basename(f)
        errs, warns = [], []
        raw = open(f, encoding='utf-8', errors='replace').read()
        m = re.search(r'<env([^>]*)>(.*?)</env>', raw, re.S)
        env_raw = m.group(2)
        flags = dict(re.findall(r'(\w+)\s*=\s*"(\w+)"', m.group(1)))

        def sbody(tag, txt=None):
            mm = re.search(r'<%s>(.*?)</%s>' % (tag, tag), env_raw if txt is None else txt, re.S)
            return mm.group(1) if mm else ''

        info = CR.atoms(CR.parse(sbody('info')))
        # §二.2注(2): 位置出现在 mis/err 部分的小物体, info 中可以省略 at/inside → 豁免
        mis_ids = set()
        for _t in ('mis', 'r', 'w'):
            for _p, _a in CR.atoms(CR.parse(sbody(_t))):
                if _p in ('at', 'inside') and _a and _a[0].isdigit():
                    mis_ids.add(_a[0])

        # --- 1. 编号升序 ---
        sort_ids = [int(x[1][0]) for x in info if x[0] == 'sort' and len(x[1]) > 1 and x[1][0].isdigit()]
        if sort_ids != sorted(sort_ids):
            errs.append('info 未按物体编号升序排列: %s' % sort_ids)
        if sort_ids and sort_ids != list(range(0, len(sort_ids))):
            pass  # 断号由 check_rules_2026 负责

        # --- 2. id 与 sort 一致性 + info 小物体完整性 ---
        objs = collections.OrderedDict()
        for p, ar in info:
            if p == 'sort' and len(ar) >= 2:
                objs[ar[0]] = {'sort': ar[1]}
        on_robot = set(ar[0] for p, ar in info if p in ('hold', 'plate') and ar and ar[0] != '0')
        # 同一行内所有字段的物体 id 必须一致(指南§二.2注4: sort 后的字段物体 id 和 sort 必须一致)
        for line in sbody('info').splitlines():
            ids = set()
            for p, ar in CR.atoms(CR.parse(line)):
                if ar and ar[0] == '0' and p in ('hold', 'plate', 'at'):
                    continue
                if ar and ar[0].isdigit():
                    ids.add(ar[0])
            if len(ids) > 1:
                errs.append('同一行字段物体 id 不一致: %s | %s' % (sorted(ids), line.strip()[:60]))
        for p, ar in info:
            if p in ('sort', 'hold', 'plate'):
                continue
            if ar and ar[0] == '0':
                continue  # robot 的 (at 0 N)
            if not ar or not ar[0].isdigit():
                errs.append('字段 %s 的物体 id 非数字: %s' % (p, ar))
                continue
            if ar[0] not in objs:
                errs.append('字段 %s 引用了未定义物体 id=%s (sort 未给出)' % (p, ar[0]))
            else:
                objs[ar[0]].setdefault('f', []).append(p)
        for i, o in objs.items():
            if i == '0':
                continue
            s = o['sort']
            kind = 'small' if s in CR.SMALLOBJS else ('container' if s in CR.CONTAINERS else 'big')
            if kind == 'small':
                if s in CR.SMALLOBJS and i not in on_robot and i not in mis_ids:
                    if 'at' not in o.get('f', []) and 'inside' not in o.get('f', []):
                        errs.append('小物体 #%s(%s) 在 info 中无 at/inside 且不在 hold/plate/err/mis (指南§二.2注2/3)' % (i, s))
            if kind == 'container':
                for need in ('type',):
                    if need not in o.get('f', []):
                        errs.append('容器 #%s(%s) 缺 %s' % (i, s, need))
            # 字段 id 与 sort 一致: (sort N x) 之后的字段第一个参数必须 == N
            for p in o.get('f', []):
                vals = [ar for pp, ar in info if pp == p and ar and ar[0] == i]
                for vv in vals:
                    if vv[0] != i:
                        errs.append('字段 %s 的 id=%s 与该物体 sort id=%s 不一致' % (p, vv[0], i))

        # --- 3. robot 位置 vs 大物体(观察项) ---
        robot_at = [ar[1] for p, ar in info if p == 'at' and ar and ar[0] == '0']
        if robot_at:
            big_same = [ar[0] for p, ar in info if p == 'at' and ar and len(ar) == 2
                        and ar[1] == robot_at[0] and ar[0] in objs and objs[ar[0]]['sort'] in CR.BIGOBJS]
            if big_same:
                warns.append('robot(at %s) 与该位置的大物体 %s 重合 -> 若裁判按"至多1个大物体"口径含robot则有风险'
                             % (robot_at[0], big_same))

        # --- 4. instr/NL ---
        ix = CR.parse(re.search(r'<instr>(.*?)</instr>', raw, re.S).group(1))
        root = [e for e in ix if isinstance(e, list) and e and e[0] == ':ins']
        cmds = [c for c in root[0][1:] if isinstance(c, list) and c and isinstance(c[0], str) and c[0].startswith(':')]
        nlbody = re.search(r'<nl>(.*?)</nl>', raw, re.S).group(1).strip()
        sents = [s.strip() for s in re.split(r'(?<=\.)\s+', nlbody) if s.strip()]
        if len(sents) != len(cmds):
            errs.append('NL 句数 %d != 指令数 %d' % (len(sents), len(cmds)))
        else:
            TASKV = {'give', 'puton', 'goto', 'putdown', 'pickup', 'open', 'close', 'putin', 'takeout'}
            INFOV = {'on', 'near', 'plate', 'inside', 'opened', 'closed'}
            for i, (c, s) in enumerate(zip(cmds, sents)):
                outer, inner = cmd_kind(c)
                if outer in ('task', 'info'):
                    pats = NL_PAT.get((outer, inner))
                elif outer == 'cons_not':
                    pats = [(r'\bDo not\b', 'Do not')] if inner in TASKV else [(r'\bmust not be\b', 'must not be')]
                elif outer == 'cons_notnot':
                    pats = [(r'\bmust be\b', 'must be')]
                else:
                    pats = None
                if pats is None:
                    warns.append('第%d句 未知指令类型 (%s,%s) (NL: %s)' % (i + 1, outer, inner, s[:40]))
                    continue
                for pat, label in pats:
                    if not re.search(pat, s, re.I):
                        errs.append('NL 第%d句 与指令 %s 不对应(缺 "%s"): %s' % (i + 1, c[0], label, s[:50]))

        # --- 4b. 比赛规则§2.7三(2): nl 中凡涉及小物体必须带颜色描述 ---
        COLORS = set("white black yellow blue green red".split())
        for _si, _s in enumerate(sents):
            _ws = re.findall(r"[A-Za-z]+", _s.lower())
            for _j, _w in enumerate(_ws):
                if _w in CR.SMALLOBJS:
                    if not any(_p in COLORS for _p in _ws[max(0, _j - 2):_j]):
                        errs.append('NL 第%d句 提到小物体 "%s" 却无颜色描述(比赛规则§2.7三(2)): %s' % (_si + 1, _w, _s[:50]))

        # --- 5. 理论满分核算 ---
        G = len([c for c in cmds if c[0] == ':task'])
        C = len([c for c in cmds if c[0] in (':cons_not', ':cons_notnot')])
        ub = 40 * G + 20 * C + 100
        ref = None
        if idx < len(answers):
            ok, acts = answers[idx]
            cost = sum(COST.get(x, 2) for x in acts)
            ref = ub - cost
            if not ok:
                errs.append('官方 validator 该题 UNSAT(不可解)')
        if ub > 1000:
            errs.append('理论满分上限 %d > 1000 (指南§五)' % ub)
        if ref is not None and ref < 200:
            errs.append('理论满分(参考方案扣%d) = %d < 200 -> 需按最优方案精确核算 (指南§五)' % (cost, ref))

        rows.append((name, G, C, ub, ref, cost if ref is not None else None, len(acts) if ref is not None else None))
        if errs:
            bad += 1
            print("\n[错误] %s" % name)
            for e in errs:
                print("   - %s" % e)
        if warns:
            print("[提示] %s" % name)
            for w in warns:
                print("   ? %s" % w)

    print("\n=== 有错误的题: %d / %d ===" % (bad, len(files)))
    print("\n=== 理论满分核算 (G=目标 C=约束) ===")
    print("  %-11s %-4s %-4s %-6s %-8s %-8s %s" % ('题', 'G', 'C', '上限', '参考分', '参考扣', '参考动作数'))
    for r in rows:
        if r[4] is None:
            print("  %-11s %-4d %-4d %-6d  %s" % (r[0], r[1], r[2], r[3], '(无testlog)'))
        else:
            mark = '' if r[4] >= 200 else '  <== 风险'
            print("  %-11s %-4d %-4d %-6d %-8d %-8d %-3d%s" % (r[0], r[1], r[2], r[3], r[4], r[5], r[6], mark))
    if rows:
        refs = [r[4] for r in rows if r[4] is not None]
        if refs:
            print("\n参考理论满分: 最低 %d / 最高 %d ; 低于200的题数 = %d" % (min(refs), max(refs), sum(1 for x in refs if x < 200)))
        print("理论满分上限: 最低 %d / 最高 %d" % (min(r[3] for r in rows), max(r[3] for r in rows)))


if __name__ == '__main__':
    main()