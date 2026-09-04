#!/usr/bin/env python3
# NLU 全量回归: 对每道NT题, 比较"客户端实际转换输出" vs "题目expected instr"
# 用法: python3 nlu_regress.py <example_stdout文件> <tests目录>
# stdout 文件 = 跑 cserver+example 时 example 的重定向输出(含"转换为结构化任务描述")
import re, sys, glob, os

def norm(s):
    # 归一化: 去多余空白, 统一小写属性顺序保留
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def canon_rule(r):
    """规则内cond条目排序, 消除 (color X red)(sort X bottle) vs (sort X bottle)(color X red) 伪差异"""
    def sort_conds(m):
        inner = m.group(1)
        conds = re.findall(r'\([^()]+\)', inner)
        return '(:cond ' + ' '.join(sorted(conds)) + ')'
    return re.sub(r'\(:cond ([^()]*(?:\([^()]*\)[^()]*)*)\)', sort_conds, r)

def rule_set(instr):
    """拆成规则条目集合(容忍顺序差异)"""
    # 每条 (:task ...) (:info ...) 用括号配深度切
    rules = []
    depth = 0; cur = ''
    body = instr
    start = body.find('(:ins')
    body = body[start+5:]
    for ch in body:
        if ch == '(': depth += 1
        if ch == ')': depth -= 1
        cur += ch
        if depth == 0 and cur.strip():
            rules.append(canon_rule(norm(cur))); cur = ''
    # 去掉最外层闭合残留
    rules = [r for r in rules if r and set(r) != {')','('}]
    return sorted(rules)

def extract_pairs(stdout_text):
    """从客户端stdout提取每案的 nl→转换后instr 序列(按出现顺序)"""
    pairs = []
    # 题目块: 以"=== 当前环境描述"开始
    blocks = stdout_text.split('=== 当前环境描述')
    for b in blocks[1:]:
        m = re.search(r'转换为结构化任务描述:\s*\n(\(:ins[^\n]*)', b)
        if m:
            pairs.append(norm(m.group(1)))
    return pairs

def extract_expected(td):
    exps = []
    for f in sorted(glob.glob(os.path.join(td, '*.xml')), key=lambda p: os.path.basename(p)):
        t = open(f, encoding='utf-8', errors='ignore').read()
        m = re.search(r'<instr>\s*(\(:ins.*?)\s*<[/]instr>', t, re.S)
        if m:
            exps.append((os.path.basename(f), norm(m.group(1))))
    return exps

def main():
    out_file, td = sys.argv[1], sys.argv[2]
    text = open(out_file, encoding='utf-8', errors='ignore').read()
    got = extract_pairs(text)
    exps = extract_expected(td)
    print(f"题数: expected={len(exps)} got={len(got)}")
    n_ok = 0
    for i, (name, exp) in enumerate(exps):
        if i >= len(got):
            print(f"{name}: 缺输出"); continue
        g = got[i]
        re_, rg_ = rule_set(exp), rule_set(g)
        if re_ == rg_:
            if norm(exp) != g:
                print(f"{name}: 规则集合一致(顺序/cond排列不同)")
            n_ok += 1; continue
        miss = [r for r in re_ if r not in rg_]
        extra = [r for r in rg_ if r not in re_]
        print(f"\n===== {name} 不匹配 =====")
        for r in miss: print(f"  [丢失] {r}")
        for r in extra: print(f"  [多余] {r}")
    print(f"\n匹配率: {n_ok}/{len(exps)}")

if __name__ == '__main__':
    main()
