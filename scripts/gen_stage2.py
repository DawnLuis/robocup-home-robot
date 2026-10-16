#!/usr/bin/env python3
"""
RoboCup服务机器人仿真赛 第二阶段出题生成器 (严格按2025出题指南)

Stage2 vs Stage1 差异:
- env: mis="on" err="on" ans="on"
- info中小物体无at/inside(位置未知)
- mis: 部分小物体正确位置(到访发现)
- err: r=错误位置(机器人初始信), w=正确位置
- ans=on: AskLoc回答可能错或"不知道"

复用stage1的30个模板(场景+instr+nl不变), 只改env:
- 每题3个小物体: 1个→mis, 1个→err(r错/w对), 1个→info(保留at/inside)
"""

import os, copy

OUT_DIR = "/home/dawnluis/Downloads/robocup-home-robot/tests/stage2"

BIG_POOL = ["plant", "couch", "chair", "sofa", "bed", "table", "workspace",
            "worktable", "teapoy", "desk", "television", "airconditioner", "washmachine"]
CONT_POOL = ["closet", "cupboard", "refrigerator", "microwave"]
SMALL_POOL = ["book", "can", "remotecontrol", "bottle", "cup"]
COLORS = ["white", "black", "yellow", "blue", "green", "red"]


class Obj:
    def __init__(self, oid, sort, color=None, ctype=None):
        self.oid, self.sort, self.color, self.ctype = oid, sort, color, ctype
        self.size = "big" if color is None else "small"


def build_scene(small_list, cont_list, big_list):
    objs, by = {}, {}
    oid = 1
    h = Obj(oid, "human"); objs[oid] = h; by["human"] = [h]; oid += 1
    for c in cont_list:
        o = Obj(oid, c, ctype="container"); objs[oid] = o; by.setdefault(c, []).append(o); oid += 1
    for b in big_list:
        o = Obj(oid, b); objs[oid] = o; by.setdefault(b, []).append(o); oid += 1
    for s, col in small_list:
        o = Obj(oid, s, color=col); objs[oid] = o; by.setdefault(s, []).append(o); oid += 1
    return objs, by


def gen_stage2_xml(t):
    """生成第二阶段XML: 小物体位置拆分到info/mis/err"""
    objs, by = build_scene(t["small"], t["cont"], t["big"])
    cont_state = t.get("cont_state", {})
    small_list = t["small"]
    big_objs = [o for oid, o in objs.items() if o.color is None and o.ctype is None and o.sort != "human"]
    cont_objs = [o for oid, o in objs.items() if o.ctype == "container"]

    # 小物体obj列表(按编号排序)
    small_objs = []
    for oid in sorted(objs):
        o = objs[oid]
        if o.color is not None:
            small_objs.append(o)

    # 分配: 第0个→mis, 第1个→err, 第2个→info(如有)
    mis_obj = small_objs[0] if len(small_objs) > 0 else None
    err_obj = small_objs[1] if len(small_objs) > 1 else None
    info_obj = small_objs[2] if len(small_objs) > 2 else None

    # 为mis_obj生成正确位置: on某个大物体 或 inside某个容器
    mis_lines = []
    if mis_obj:
        # 选一个大物体位置(不是human)
        target_big = big_objs[0] if big_objs else None
        target_cont = cont_objs[0] if cont_objs else None
        # 优先放容器内(更有趣), 否则放大物体上
        if target_cont and mis_obj.oid % 2 == 0:
            mis_lines.append(f"(inside {mis_obj.oid} {target_cont.oid})")
        elif target_big:
            mis_lines.append(f"(at {mis_obj.oid} {target_big.oid})")
        elif target_cont:
            mis_lines.append(f"(inside {mis_obj.oid} {target_cont.oid})")

    # 为err_obj生成 r=正确位置, w=错误位置
    # ★平台实际语义(platform.cpp): <r>→correct_info(评分用正确值), <w>→erroneous_info(传给机器人误导)
    # 与出题指南字面(r=错误/w=正确)相反! 故: r=正确位置, w=错误位置
    err_r, err_w = "", ""
    if err_obj:
        # 正确位置: on第二个大物体 或 inside容器
        correct_big = big_objs[1] if len(big_objs) > 1 else (big_objs[0] if big_objs else None)
        correct_cont = cont_objs[1] if len(cont_objs) > 1 else (cont_objs[0] if cont_objs else None)
        # 错误位置: on不同大物体 或 inside不同容器
        wrong_big = big_objs[2] if len(big_objs) > 2 else (big_objs[0] if big_objs else None)
        wrong_cont = cont_objs[0] if cont_objs else None

        # 正确(r): 放容器内
        if correct_cont:
            err_r = f"(inside {err_obj.oid} {correct_cont.oid})"
        elif correct_big:
            err_r = f"(at {err_obj.oid} {correct_big.oid})"

        # 错误(w): 放不同位置
        if wrong_cont and wrong_cont.oid != (correct_cont.oid if correct_cont else -1):
            err_w = f"(inside {err_obj.oid} {wrong_cont.oid})"
        elif wrong_big:
            err_w = f"(at {err_obj.oid} {wrong_big.oid})"
        # 若r和w相同则换一个错误位置
        if err_w == err_r:
            if wrong_cont:
                err_w = f"(inside {err_obj.oid} {wrong_cont.oid})"
            elif wrong_big:
                err_w = f"(at {err_obj.oid} {wrong_big.oid})"

    # info: 小物体去掉at/inside, 但info_obj保留正确位置
    info_lines = [f"(hold {t.get('hold',0)}) (plate {t.get('plate',0)}) (at 0 {t.get('at',5)})"]
    for oid in sorted(objs):
        o = objs[oid]
        line = f"(sort {oid} {o.sort}) (size {oid} {o.size})"
        if o.color: line += f" (color {oid} {o.color})"
        if o.ctype:
            line += f" (type {oid} container)"
            st = cont_state.get(o.sort, "closed")
            line += f" ({st} {oid})"
        # 大物体和human: 保留at
        if o.color is None:
            line += f" (at {oid} {oid})"
        else:
            # 小物体: 只有info_obj保留at/inside, 其他去掉
            if info_obj and o.oid == info_obj.oid:
                # info_obj放一个大物体上
                target_big = big_objs[-1] if big_objs else None
                if target_big:
                    line += f" (at {oid} {target_big.oid})"
                else:
                    line += f" (at {oid} {oid})"
            # 其他小物体: 无at/inside (位置未知)
        info_lines.append(line)
    info = "\n".join(info_lines)

    # mis
    mis_content = "\n    ".join(mis_lines) if mis_lines else ""

    # err
    err_r_content = err_r
    err_w_content = err_w

    # instr/nl (与stage1完全相同)
    instr_parts, nl_parts = [], []
    for itmpl, ntmpl in t["instrs"]:
        instr_parts.append("    " + itmpl)
        nl_parts.append(ntmpl)
    instr = "\n".join(instr_parts)
    nl = "\n".join(nl_parts)

    return f'''<?xml version="1.0" encoding="utf-8"?>
<test>
<env mis="on" err="on" ans="on">
    <info>
    {info}
    </info>
    <mis>
    {mis_content}
    </mis>
    <err>
        <r>{err_r_content}</r>
        <w>{err_w_content}</w>
    </err>
    <extra>
    </extra>
</env>
<instr>
(:ins
{instr}
)
</instr>
<nl>
{nl}
</nl>
</test>
'''


def mk(small, cont, big, instrs, cont_state=None, **kw):
    t = {"small": small, "cont": cont, "big": big, "instrs": instrs}
    if cont_state: t["cont_state"] = cont_state
    t.update(kw)
    return t


def write_all():
    os.makedirs(OUT_DIR, exist_ok=True)
    templates = build_templates()
    # 写test.list
    list_lines = []
    for i, t in enumerate(templates):
        fname = f"18-{i+1:02d}.xml"
        path = os.path.join(OUT_DIR, fname)
        with open(path, "w", encoding="utf-8") as f:
            f.write(gen_stage2_xml(t))
        list_lines.append(fname)
    # 写test.list
    with open(os.path.join(OUT_DIR, "test.list"), "w", encoding="utf-8") as f:
        f.write("\n".join(list_lines) + "\n")
    print(f"生成 {len(templates)} 题到 {OUT_DIR}")


def build_templates():
    """30个模板, 与stage1相同场景+instr+nl"""
    T = []

    # 1-5: 基础搬运类
    T += [
        mk([("book","red"),("cup","blue"),("can","green")], ["closet","microwave"], ["worktable","plant","sofa"], [
            ("(:task (puton X Y) (:cond (sort X book) (color X red) (sort Y worktable)))", "Put the red book on the worktable."),
            ("(:task (putin X Y) (:cond (sort X cup) (color X blue) (sort Y closet) (type Y container)))", "Put the blue cup in the closet."),
            ("(:task (goto X) (:cond (sort X plant)))", "Go to the plant."),
            ("(:task (pickup X) (:cond (sort X can) (color X green)))", "Pick up the green can."),
            ("(:cons_not (:task (puton X Y) (:cond (sort X book) (color X red) (sort Y sofa))))", "Do not put the red book on the sofa."),
            ("(:cons_not (:task (putin X Y) (:cond (sort X cup) (color X blue) (sort Y microwave) (type Y container))))", "Do not put the blue cup in the microwave."),
        ]),
        mk([("book","yellow"),("bottle","black"),("cup","white")], ["cupboard","refrigerator"], ["table","desk","bed"], [
            ("(:task (puton X Y) (:cond (sort X book) (color X yellow) (sort Y table)))", "Put the yellow book on the table."),
            ("(:task (putin X Y) (:cond (sort X bottle) (color X black) (sort Y refrigerator) (type Y container)))", "Put the black bottle in the refrigerator."),
            ("(:task (goto X) (:cond (sort X desk)))", "Go to the desk."),
            ("(:task (pickup X) (:cond (sort X cup) (color X white)))", "Pick up the white cup."),
            ("(:cons_not (:task (puton X Y) (:cond (sort X book) (color X yellow) (sort Y bed))))", "Do not put the yellow book on the bed."),
        ]),
        mk([("can","black"),("remotecontrol","green"),("book","white")], ["microwave","cupboard"], ["sofa","chair","teapoy"], [
            ("(:task (puton X Y) (:cond (sort X can) (color X black) (sort Y sofa)))", "Put the black can on the sofa."),
            ("(:task (putin X Y) (:cond (sort X remotecontrol) (color X green) (sort Y cupboard) (type Y container)))", "Put the green remotecontrol in the cupboard."),
            ("(:task (goto X) (:cond (sort X chair)))", "Go to the chair."),
            ("(:task (pickup X) (:cond (sort X book) (color X white)))", "Pick up the white book."),
            ("(:cons_not (:task (putin X Y) (:cond (sort X remotecontrol) (color X green) (sort Y microwave) (type Y container))))", "Do not put the green remotecontrol in the microwave."),
        ]),
        mk([("bottle","blue"),("cup","red"),("can","yellow")], ["closet","refrigerator"], ["worktable","couch","plant"], [
            ("(:task (puton X Y) (:cond (sort X bottle) (color X blue) (sort Y worktable)))", "Put the blue bottle on the worktable."),
            ("(:task (putin X Y) (:cond (sort X cup) (color X red) (sort Y closet) (type Y container)))", "Put the red cup in the closet."),
            ("(:task (goto X) (:cond (sort X couch)))", "Go to the couch."),
            ("(:task (pickup X) (:cond (sort X can) (color X yellow)))", "Pick up the yellow can."),
            ("(:cons_not (:task (putin X Y) (:cond (sort X cup) (color X red) (sort Y refrigerator) (type Y container))))", "Do not put the red cup in the refrigerator."),
        ]),
        mk([("book","green"),("can","white"),("remotecontrol","blue")], ["cupboard","closet"], ["desk","bed","table"], [
            ("(:task (puton X Y) (:cond (sort X book) (color X green) (sort Y desk)))", "Put the green book on the desk."),
            ("(:task (putin X Y) (:cond (sort X can) (color X white) (sort Y closet) (type Y container)))", "Put the white can in the closet."),
            ("(:task (goto X) (:cond (sort X table)))", "Go to the table."),
            ("(:task (pickup X) (:cond (sort X remotecontrol) (color X blue)))", "Pick up the blue remotecontrol."),
            ("(:cons_not (:task (puton X Y) (:cond (sort X book) (color X green) (sort Y bed))))", "Do not put the green book on the bed."),
        ]),
    ]

    # 6-10: takeout/putdown + info + cons_notnot
    T += [
        mk([("bottle","yellow"),("remotecontrol","white"),("book","green")], ["cupboard","refrigerator"], ["desk","chair","table"], [
            ("(:info (opened X) (:cond (sort X cupboard)))", "The cupboard is opened."),
            ("(:info (closed X) (:cond (sort X refrigerator)))", "The refrigerator is closed."),
            ("(:task (takeout X Y) (:cond (sort X bottle) (color X yellow) (sort Y cupboard) (type Y container)))", "Take out the yellow bottle from the cupboard."),
            ("(:task (putdown X) (:cond (sort X remotecontrol) (color X white)))", "Put down the white remotecontrol."),
            ("(:cons_notnot (:info (on X Y) (:cond (sort X book) (color X green) (sort Y desk))))", "There must be a green book on the desk."),
            ("(:task (puton X Y) (:cond (sort X remotecontrol) (color X white) (sort Y chair)))", "Put the white remotecontrol on the chair."),
        ], cont_state={"cupboard":"opened","refrigerator":"closed"}),
        mk([("cup","white"),("bottle","blue"),("book","red")], ["microwave","closet"], ["sofa","plant","worktable"], [
            ("(:info (closed X) (:cond (sort X closet)))", "The closet is closed."),
            ("(:task (takeout X Y) (:cond (sort X cup) (color X white) (sort Y microwave) (type Y container)))", "Take out the white cup from the microwave."),
            ("(:task (putdown X) (:cond (sort X bottle) (color X blue)))", "Put down the blue bottle."),
            ("(:cons_notnot (:info (inside X Y) (:cond (sort X book) (color X red) (sort Y closet) (type Y container))))", "There must be a red book in the closet."),
            ("(:task (puton X Y) (:cond (sort X book) (color X red) (sort Y sofa)))", "Put the red book on the sofa."),
        ], cont_state={"closet":"closed","microwave":"opened"}),
        mk([("can","green"),("remotecontrol","black"),("cup","yellow")], ["refrigerator","cupboard"], ["chair","desk","teapoy"], [
            ("(:info (opened X) (:cond (sort X refrigerator)))", "The refrigerator is opened."),
            ("(:task (takeout X Y) (:cond (sort X can) (color X green) (sort Y refrigerator) (type Y container)))", "Take out the green can from the refrigerator."),
            ("(:task (putdown X) (:cond (sort X remotecontrol) (color X black)))", "Put down the black remotecontrol."),
            ("(:cons_notnot (:info (on X Y) (:cond (sort X cup) (color X yellow) (sort Y teapoy))))", "There must be a yellow cup on the teapoy."),
        ], cont_state={"refrigerator":"opened","cupboard":"closed"}),
        mk([("bottle","red"),("book","black"),("can","blue")], ["closet","microwave"], ["worktable","couch","bed"], [
            ("(:info (closed X) (:cond (sort X microwave)))", "The microwave is closed."),
            ("(:task (takeout X Y) (:cond (sort X bottle) (color X red) (sort Y closet) (type Y container)))", "Take out the red bottle from the closet."),
            ("(:task (putdown X) (:cond (sort X book) (color X black)))", "Put down the black book."),
            ("(:cons_notnot (:info (inside X Y) (:cond (sort X can) (color X blue) (sort Y closet) (type Y container))))", "There must be a blue can in the closet."),
        ], cont_state={"closet":"closed","microwave":"closed"}),
        mk([("remotecontrol","yellow"),("cup","green"),("bottle","white")], ["cupboard","refrigerator"], ["table","sofa","desk"], [
            ("(:info (opened X) (:cond (sort X cupboard)))", "The cupboard is opened."),
            ("(:task (takeout X Y) (:cond (sort X remotecontrol) (color X yellow) (sort Y cupboard) (type Y container)))", "Take out the yellow remotecontrol from the cupboard."),
            ("(:task (putdown X) (:cond (sort X cup) (color X green)))", "Put down the green cup."),
            ("(:cons_notnot (:info (on X Y) (:cond (sort X bottle) (color X white) (sort Y table))))", "There must be a white bottle on the table."),
        ], cont_state={"cupboard":"opened","refrigerator":"closed"}),
    ]

    # 11-15: open/close + give + 混合
    T += [
        mk([("book","black"),("cup","yellow"),("bottle","white")], ["microwave","closet"], ["bed","worktable"], [
            ("(:task (open X) (:cond (sort X closet) (type X container)))", "Open the closet."),
            ("(:task (close X) (:cond (sort X microwave) (type X container)))", "Close the microwave."),
            ("(:task (putin X Y) (:cond (sort X cup) (color X yellow) (sort Y closet) (type Y container)))", "Put the yellow cup in the closet."),
            ("(:task (give human X) (:cond (sort X book) (color X black)))", "Give the black book to the human."),
            ("(:cons_not (:task (putdown X) (:cond (sort X bottle) (color X white))))", "Do not put down the white bottle."),
        ], cont_state={"closet":"closed","microwave":"opened"}),
        mk([("can","red"),("book","green"),("remotecontrol","white")], ["refrigerator","closet"], ["couch","desk"], [
            ("(:task (open X) (:cond (sort X refrigerator) (type X container)))", "Open the refrigerator."),
            ("(:task (close X) (:cond (sort X closet) (type X container)))", "Close the closet."),
            ("(:task (putin X Y) (:cond (sort X can) (color X red) (sort Y refrigerator) (type Y container)))", "Put the red can in the refrigerator."),
            ("(:task (give human X) (:cond (sort X remotecontrol) (color X white)))", "Give the white remotecontrol to the human."),
        ], cont_state={"refrigerator":"closed","closet":"opened"}),
        mk([("bottle","black"),("cup","white"),("book","blue")], ["cupboard","microwave"], ["sofa","plant"], [
            ("(:task (open X) (:cond (sort X cupboard) (type X container)))", "Open the cupboard."),
            ("(:task (close X) (:cond (sort X microwave) (type X container)))", "Close the microwave."),
            ("(:task (putin X Y) (:cond (sort X bottle) (color X black) (sort Y cupboard) (type Y container)))", "Put the black bottle in the cupboard."),
            ("(:task (give human X) (:cond (sort X cup) (color X white)))", "Give the white cup to the human."),
            ("(:cons_notnot (:info (on X Y) (:cond (sort X book) (color X blue) (sort Y sofa))))", "There must be a blue book on the sofa."),
        ], cont_state={"cupboard":"closed","microwave":"opened"}),
        mk([("remotecontrol","green"),("can","yellow"),("book","white")], ["microwave","cupboard"], ["desk","bed","table"], [
            ("(:task (open X) (:cond (sort X microwave) (type X container)))", "Open the microwave."),
            ("(:task (close X) (:cond (sort X cupboard) (type X container)))", "Close the cupboard."),
            ("(:task (putin X Y) (:cond (sort X remotecontrol) (color X green) (sort Y microwave) (type Y container)))", "Put the green remotecontrol in the microwave."),
            ("(:task (give human X) (:cond (sort X book) (color X white)))", "Give the white book to the human."),
            ("(:cons_not (:task (puton X Y) (:cond (sort X can) (color X yellow) (sort Y desk))))", "Do not put the yellow can on the desk."),
        ], cont_state={"microwave":"closed","cupboard":"opened"}),
        mk([("cup","black"),("bottle","yellow"),("remotecontrol","red")], ["closet","refrigerator"], ["worktable","couch","chair"], [
            ("(:task (open X) (:cond (sort X closet) (type X container)))", "Open the closet."),
            ("(:task (close X) (:cond (sort X refrigerator) (type X container)))", "Close the refrigerator."),
            ("(:task (putin X Y) (:cond (sort X cup) (color X black) (sort Y closet) (type Y container)))", "Put the black cup in the closet."),
            ("(:task (give human X) (:cond (sort X bottle) (color X yellow)))", "Give the yellow bottle to the human."),
        ], cont_state={"closet":"closed","refrigerator":"opened"}),
    ]

    # 16-20: 多任务综合
    T += [
        mk([("book","red"),("can","blue"),("cup","green")], ["microwave","cupboard"], ["worktable","plant","sofa","desk"], [
            ("(:info (inside X Y) (:cond (sort X can) (color X blue) (sort Y microwave) (type Y container)))", "The blue can is in the microwave."),
            ("(:task (puton X Y) (:cond (sort X book) (color X red) (sort Y worktable)))", "Put the red book on the worktable."),
            ("(:task (putin X Y) (:cond (sort X cup) (color X green) (sort Y cupboard) (type Y container)))", "Put the green cup in the cupboard."),
            ("(:cons_notnot (:info (on X Y) (:cond (sort X book) (color X red) (sort Y plant))))", "There must be a red book on the plant."),
            ("(:cons_not (:task (putin X Y) (:cond (sort X can) (color X blue) (sort Y cupboard) (type Y container))))", "Do not put the blue can in the cupboard."),
            ("(:task (goto X) (:cond (sort X sofa)))", "Go to the sofa."),
        ], cont_state={"microwave":"opened","cupboard":"closed"}),
        mk([("bottle","white"),("book","yellow"),("remotecontrol","green")], ["refrigerator","closet"], ["table","chair","couch","bed"], [
            ("(:info (on X Y) (:cond (sort X bottle) (color X white) (sort Y table)))", "The white bottle is on the table."),
            ("(:task (takeout X Y) (:cond (sort X remotecontrol) (color X green) (sort Y refrigerator) (type Y container)))", "Take out the green remotecontrol from the refrigerator."),
            ("(:task (puton X Y) (:cond (sort X book) (color X yellow) (sort Y chair)))", "Put the yellow book on the chair."),
            ("(:cons_notnot (:info (inside X Y) (:cond (sort X book) (color X yellow) (sort Y closet) (type Y container))))", "There must be a yellow book in the closet."),
            ("(:cons_not (:task (puton X Y) (:cond (sort X bottle) (color X white) (sort Y couch))))", "Do not put the white bottle on the couch."),
        ], cont_state={"refrigerator":"opened","closet":"closed"}),
        mk([("can","black"),("cup","red"),("book","green")], ["cupboard","microwave"], ["desk","sofa","plant","worktable"], [
            ("(:info (opened X) (:cond (sort X cupboard)))", "The cupboard is opened."),
            ("(:task (putin X Y) (:cond (sort X can) (color X black) (sort Y cupboard) (type Y container)))", "Put the black can in the cupboard."),
            ("(:task (puton X Y) (:cond (sort X cup) (color X red) (sort Y desk)))", "Put the red cup on the desk."),
            ("(:cons_notnot (:info (on X Y) (:cond (sort X book) (color X green) (sort Y sofa))))", "There must be a green book on the sofa."),
            ("(:cons_not (:task (putin X Y) (:cond (sort X cup) (color X red) (sort Y microwave) (type Y container))))", "Do not put the red cup in the microwave."),
        ], cont_state={"cupboard":"opened","microwave":"closed"}),
        mk([("remotecontrol","white"),("bottle","black"),("can","yellow")], ["closet","refrigerator"], ["worktable","chair","teapoy","bed"], [
            ("(:info (closed X) (:cond (sort X refrigerator)))", "The refrigerator is closed."),
            ("(:task (takeout X Y) (:cond (sort X remotecontrol) (color X white) (sort Y closet) (type Y container)))", "Take out the white remotecontrol from the closet."),
            ("(:task (puton X Y) (:cond (sort X bottle) (color X black) (sort Y worktable)))", "Put the black bottle on the worktable."),
            ("(:cons_notnot (:info (inside X Y) (:cond (sort X can) (color X yellow) (sort Y refrigerator) (type Y container))))", "There must be a yellow can in the refrigerator."),
            ("(:cons_not (:task (puton X Y) (:cond (sort X bottle) (color X black) (sort Y bed))))", "Do not put the black bottle on the bed."),
        ], cont_state={"closet":"opened","refrigerator":"closed"}),
        mk([("book","blue"),("cup","white"),("bottle","green")], ["microwave","cupboard"], ["sofa","desk","table","plant"], [
            ("(:info (inside X Y) (:cond (sort X book) (color X blue) (sort Y cupboard) (type Y container)))", "The blue book is in the cupboard."),
            ("(:task (putin X Y) (:cond (sort X cup) (color X white) (sort Y microwave) (type Y container)))", "Put the white cup in the microwave."),
            ("(:task (puton X Y) (:cond (sort X bottle) (color X green) (sort Y sofa)))", "Put the green bottle on the sofa."),
            ("(:cons_notnot (:info (on X Y) (:cond (sort X cup) (color X white) (sort Y desk))))", "There must be a white cup on the desk."),
            ("(:cons_not (:task (putin X Y) (:cond (sort X book) (color X blue) (sort Y microwave) (type Y container))))", "Do not put the blue book in the microwave."),
        ], cont_state={"microwave":"opened","cupboard":"closed"}),
    ]

    # 21-25
    T += [
        mk([("can","white"),("book","red"),("remotecontrol","blue")], ["refrigerator","microwave"], ["worktable","chair","sofa","table"], [
            ("(:info (opened X) (:cond (sort X microwave)))", "The microwave is opened."),
            ("(:info (closed X) (:cond (sort X refrigerator)))", "The refrigerator is closed."),
            ("(:task (putin X Y) (:cond (sort X can) (color X white) (sort Y refrigerator) (type Y container)))", "Put the white can in the refrigerator."),
            ("(:task (puton X Y) (:cond (sort X book) (color X red) (sort Y worktable)))", "Put the red book on the worktable."),
            ("(:cons_notnot (:info (on X Y) (:cond (sort X remotecontrol) (color X blue) (sort Y chair))))", "There must be a blue remotecontrol on the chair."),
            ("(:cons_not (:task (puton X Y) (:cond (sort X book) (color X red) (sort Y sofa))))", "Do not put the red book on the sofa."),
        ], cont_state={"microwave":"opened","refrigerator":"closed"}),
        mk([("bottle","yellow"),("cup","black"),("book","white")], ["closet","cupboard"], ["desk","bed","plant","couch"], [
            ("(:info (closed X) (:cond (sort X closet)))", "The closet is closed."),
            ("(:task (takeout X Y) (:cond (sort X bottle) (color X yellow) (sort Y closet) (type Y container)))", "Take out the yellow bottle from the closet."),
            ("(:task (putin X Y) (:cond (sort X cup) (color X black) (sort Y cupboard) (type Y container)))", "Put the black cup in the cupboard."),
            ("(:cons_notnot (:info (on X Y) (:cond (sort X book) (color X white) (sort Y desk))))", "There must be a white book on the desk."),
            ("(:cons_not (:task (putin X Y) (:cond (sort X cup) (color X black) (sort Y closet) (type Y container))))", "Do not put the black cup in the closet."),
        ], cont_state={"closet":"closed","cupboard":"opened"}),
        mk([("remotecontrol","green"),("can","red"),("bottle","blue")], ["microwave","refrigerator"], ["sofa","worktable","chair","teapoy"], [
            ("(:info (inside X Y) (:cond (sort X remotecontrol) (color X green) (sort Y microwave) (type Y container)))", "The green remotecontrol is in the microwave."),
            ("(:task (puton X Y) (:cond (sort X can) (color X red) (sort Y sofa)))", "Put the red can on the sofa."),
            ("(:task (putin X Y) (:cond (sort X bottle) (color X blue) (sort Y refrigerator) (type Y container)))", "Put the blue bottle in the refrigerator."),
            ("(:cons_notnot (:info (on X Y) (:cond (sort X can) (color X red) (sort Y worktable))))", "There must be a red can on the worktable."),
        ], cont_state={"microwave":"opened","refrigerator":"closed"}),
        mk([("book","black"),("cup","green"),("can","white")], ["cupboard","closet"], ["table","desk","sofa","bed"], [
            ("(:info (opened X) (:cond (sort X cupboard)))", "The cupboard is opened."),
            ("(:task (putin X Y) (:cond (sort X book) (color X black) (sort Y cupboard) (type Y container)))", "Put the black book in the cupboard."),
            ("(:task (puton X Y) (:cond (sort X cup) (color X green) (sort Y table)))", "Put the green cup on the table."),
            ("(:cons_notnot (:info (inside X Y) (:cond (sort X can) (color X white) (sort Y closet) (type Y container))))", "There must be a white can in the closet."),
            ("(:cons_not (:task (puton X Y) (:cond (sort X cup) (color X green) (sort Y sofa))))", "Do not put the green cup on the sofa."),
        ], cont_state={"cupboard":"opened","closet":"closed"}),
        mk([("bottle","red"),("remotecontrol","black"),("book","yellow")], ["refrigerator","microwave"], ["worktable","couch","plant","desk"], [
            ("(:info (closed X) (:cond (sort X refrigerator)))", "The refrigerator is closed."),
            ("(:task (takeout X Y) (:cond (sort X remotecontrol) (color X black) (sort Y refrigerator) (type Y container)))", "Take out the black remotecontrol from the refrigerator."),
            ("(:task (putin X Y) (:cond (sort X bottle) (color X red) (sort Y microwave) (type Y container)))", "Put the red bottle in the microwave."),
            ("(:cons_notnot (:info (on X Y) (:cond (sort X book) (color X yellow) (sort Y worktable))))", "There must be a yellow book on the worktable."),
        ], cont_state={"refrigerator":"closed","microwave":"opened"}),
    ]

    # 26-30
    T += [
        mk([("cup","yellow"),("book","blue"),("can","green")], ["closet","cupboard","microwave"], ["sofa","desk","table"], [
            ("(:task (open X) (:cond (sort X closet) (type X container)))", "Open the closet."),
            ("(:task (putin X Y) (:cond (sort X cup) (color X yellow) (sort Y closet) (type Y container)))", "Put the yellow cup in the closet."),
            ("(:task (goto X) (:cond (sort X sofa)))", "Go to the sofa."),
            ("(:task (puton X Y) (:cond (sort X book) (color X blue) (sort Y desk)))", "Put the blue book on the desk."),
            ("(:cons_notnot (:info (on X Y) (:cond (sort X can) (color X green) (sort Y table))))", "There must be a green can on the table."),
        ], cont_state={"closet":"closed","cupboard":"opened","microwave":"closed"}),
        mk([("bottle","green"),("remotecontrol","red"),("book","white")], ["refrigerator","cupboard"], ["chair","bed","worktable","plant"], [
            ("(:task (close X) (:cond (sort X refrigerator) (type X container)))", "Close the refrigerator."),
            ("(:task (takeout X Y) (:cond (sort X remotecontrol) (color X red) (sort Y cupboard) (type Y container)))", "Take out the red remotecontrol from the cupboard."),
            ("(:task (puton X Y) (:cond (sort X bottle) (color X green) (sort Y chair)))", "Put the green bottle on the chair."),
            ("(:cons_notnot (:info (inside X Y) (:cond (sort X book) (color X white) (sort Y refrigerator) (type Y container))))", "There must be a white book in the refrigerator."),
        ], cont_state={"refrigerator":"opened","cupboard":"opened"}),
        mk([("can","blue"),("cup","black"),("bottle","white")], ["microwave","closet","cupboard"], ["worktable","sofa","teapoy"], [
            ("(:task (open X) (:cond (sort X microwave) (type X container)))", "Open the microwave."),
            ("(:task (putin X Y) (:cond (sort X can) (color X blue) (sort Y microwave) (type Y container)))", "Put the blue can in the microwave."),
            ("(:task (puton X Y) (:cond (sort X cup) (color X black) (sort Y worktable)))", "Put the black cup on the worktable."),
            ("(:task (give human X) (:cond (sort X bottle) (color X white)))", "Give the white bottle to the human."),
            ("(:cons_not (:task (putin X Y) (:cond (sort X can) (color X blue) (sort Y closet) (type Y container))))", "Do not put the blue can in the closet."),
        ], cont_state={"microwave":"closed","closet":"opened","cupboard":"closed"}),
        mk([("book","yellow"),("remotecontrol","green"),("cup","red")], ["cupboard","refrigerator","microwave"], ["desk","chair","sofa","bed"], [
            ("(:task (close X) (:cond (sort X cupboard) (type X container)))", "Close the cupboard."),
            ("(:task (putin X Y) (:cond (sort X book) (color X yellow) (sort Y cupboard) (type Y container)))", "Put the yellow book in the cupboard."),
            ("(:task (puton X Y) (:cond (sort X remotecontrol) (color X green) (sort Y desk)))", "Put the green remotecontrol on the desk."),
            ("(:cons_notnot (:info (on X Y) (:cond (sort X cup) (color X red) (sort Y chair))))", "There must be a red cup on the chair."),
            ("(:cons_not (:task (putin X Y) (:cond (sort X book) (color X yellow) (sort Y refrigerator) (type Y container))))", "Do not put the yellow book in the refrigerator."),
        ], cont_state={"cupboard":"closed","refrigerator":"opened","microwave":"closed"}),
        mk([("bottle","black"),("can","red"),("book","green")], ["closet","microwave","refrigerator"], ["worktable","sofa","plant","table"], [
            ("(:task (open X) (:cond (sort X closet) (type X container)))", "Open the closet."),
            ("(:task (close X) (:cond (sort X microwave) (type X container)))", "Close the microwave."),
            ("(:task (putin X Y) (:cond (sort X bottle) (color X black) (sort Y closet) (type Y container)))", "Put the black bottle in the closet."),
            ("(:task (puton X Y) (:cond (sort X can) (color X red) (sort Y worktable)))", "Put the red can on the worktable."),
            ("(:cons_notnot (:info (on X Y) (:cond (sort X book) (color X green) (sort Y sofa))))", "There must be a green book on the sofa."),
        ], cont_state={"closet":"closed","microwave":"opened","refrigerator":"closed"}),
    ]

    return T


if __name__ == "__main__":
    write_all()
