#!/usr/bin/env python3
"""对照2025出题指南检查服务机器人仿真测试题XML格式合规性。

用法:
    python3 check_rules2.py [测试目录]   # 默认 tests/example/

覆盖检查: 编号断号 / 小物体缺color(info与instr) / 容器缺type / info未以hold开头 /
NL句数vs instr项数 / NL句号结尾 / instr未知谓词 / 容器任务缺type / 括号匹配。

注意: 该脚本查的是**出题合规性**(交题扣分点), 不影响NLU解析正确性。
NLU调试用参考 references/nlu-bug-analysis-20260831.md 的方法论(harnes对比NLU输出vs expected instr)。
"""
import os, re, sys

TEST_DIR = os.path.expanduser("~/Downloads/Planner-release-2025/Planner-release-ubuntu18/tests/example")
if len(sys.argv) > 1:
    TEST_DIR = sys.argv[1]

SMALL_OBJECTS = {"book", "can", "remotecontrol", "bottle", "cup"}
BIG_OBJECTS = {"human", "plant", "couch", "chair", "sofa", "bed", "table",
               "workspace", "worktable", "teapoy", "desk", "television",
               "airconditioner", "washmachine"}
CONTAINERS = {"closet", "cupboard", "refrigerator", "microwave"}
VALID_TASKS = {"give", "puton", "goto", "putdown", "pickup", "open", "close", "putin", "takeout"}
VALID_INFOS = {"on", "near", "plate", "inside", "opened", "closed"}


def parse_test_xml(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    info_match = re.search(r'<info>\s*(.*?)\s*</info>', content, re.DOTALL)
    instr_match = re.search(r'<instr>\s*(.*?)\s*</instr>', content, re.DOTALL)
    nl_match = re.search(r'<nl>\s*(.*?)\s*</nl>', content, re.DOTALL)
    return (info_match.group(1) if info_match else "",
            instr_match.group(1) if instr_match else "",
            nl_match.group(1) if nl_match else "")


def parse_sexp(text):
    items, depth, start = [], 0, 0
    for i, c in enumerate(text):
        if c == '(':
            if depth == 0: start = i
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                s = text[start:i+1].strip()
                if s: items.append(s)
    return items


def check_file(filepath):
    errors = []
    info_text, instr_text, nl_text = parse_test_xml(filepath)

    facts = [f.strip('()').split() for f in parse_sexp(info_text) if f.strip('()').split()]
    objects = {}
    for fact in facts:
        if not fact: continue
        key = fact[0]
        if key == "sort": objects.setdefault(int(fact[1]), {})["sort"] = fact[2]
        elif key == "size": objects.setdefault(int(fact[1]), {})["size"] = fact[2]
        elif key == "color": objects.setdefault(int(fact[1]), {})["color"] = fact[2]
        elif key == "type": objects.setdefault(int(fact[1]), {})["type"] = fact[2]

    obj_ids = sorted(objects.keys())
    for i in range(len(obj_ids) - 1):
        if obj_ids[i+1] - obj_ids[i] != 1:
            errors.append(f"编号断号: {obj_ids[i]}→{obj_ids[i+1]}")
    for oid in obj_ids:
        obj = objects[oid]
        if obj.get("size") == "small" and "color" not in obj:
            errors.append(f"物体{oid}({obj.get('sort','?')})小物体缺color")
        if obj.get("sort") in CONTAINERS and obj.get("type") != "container":
            errors.append(f"物体{oid}({obj['sort']})容器缺(type * container)")
    if not info_text.strip().startswith("(hold"):
        errors.append("info未以hold开头")

    instr_clean = instr_text.strip()
    if instr_clean.startswith("(:ins"): instr_clean = instr_clean[5:]
    if instr_clean.endswith(")"): instr_clean = instr_clean[:-1]
    instr_items = parse_sexp(instr_clean)

    for item in instr_items:
        rule_type = item.strip().split(None, 1)[0]
        if rule_type == ":task":
            pm = re.search(r':task\s+\((\w+)', item)
            if pm:
                pred = pm.group(1)
                if pred not in VALID_TASKS: errors.append(f"未知任务谓词: {pred}")
                if pred in ("putin", "takeout") and "(type Y container)" not in item:
                    errors.append(f"容器任务{pred}缺(type Y container)")
                if pred in ("open", "close") and "(type X container)" not in item:
                    errors.append(f"容器任务{pred}缺(type X container)")
        elif rule_type == ":info":
            pm = re.search(r':info\s+\((\w+)', item)
            if pm and pm.group(1) not in VALID_INFOS:
                errors.append(f"未知信息谓词: {pm.group(1)}")
        elif rule_type in (":cons_not", ":cons_notnot"):
            if "(:task" not in item and "(:info" not in item:
                errors.append("cons缺内层task/info")
        if item.count('(') != item.count(')'):
            errors.append(f"括号不匹配: {item[:50]}")

    nl_sentences = [s.strip() for s in re.split(r'[.!?]+(?:\s+|$)', nl_text) if s.strip()]
    if len(nl_sentences) != len(instr_items):
        errors.append(f"NL句数({len(nl_sentences)})≠instr项数({len(instr_items)})")
    for line in [l.strip() for l in nl_text.strip().split('\n') if l.strip()]:
        if line and not line.endswith('.'):
            errors.append(f"NL句未以句号结尾: ...{line[-30:]}")
    return errors, len(instr_items), len(nl_sentences)


def main():
    existing = []
    for tid in range(50, 100):
        path = os.path.join(TEST_DIR, f"{tid}.xml")
        if os.path.exists(path): existing.append((tid, path))
    all_err, err_files, ok = [], [], []
    for tid, path in existing:
        errors, ni, nn = check_file(path)
        if errors:
            err_files.append((tid, errors, ni, nn))
            all_err.extend([(tid, e) for e in errors])
        else:
            ok.append(tid)
    print(f"=== {len(existing)}题: 合规{len(ok)} ({', '.join(map(str,ok))}), 有问题{len(err_files)} (共{len(all_err)}处) ===")
    for tid, errors, ni, nn in err_files:
        print(f"{tid}.xml (instr={ni}, nl={nn}):")
        for e in errors: print(f"  - {e}")
        print()


if __name__ == "__main__":
    main()
