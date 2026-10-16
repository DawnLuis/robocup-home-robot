# RoboCup 服务机器人仿真赛项 · 参赛项目

中国机器人大赛暨 RoboCup 机器人世界杯中国赛 · 服务机器人赛项 · 服务机器人仿真项目
参赛队伍：**Dawnluis**（重庆科技大学）

本仓库包含两类内容：

1. **参赛程序**（`example/`）—— 比赛时提交的客户端代码；
2. **自出赛题**（`tests/`）—— 每阶段需提交 30 道题目（未提交队伍无抽题资格），
   以及配套的出题生成器与合规检查工具（`scripts/`）。

---

## 一、目录结构

```
example/            参赛程序（客户端）
  devil.cpp/.hpp          规划主逻辑（任务排序、执行、约束感知）
  environment_manager.*   环境状态解析与维护
  instruction_parser.*    指令语言（:ins）解析
  nlu.*                   自然语言（受限英语）解析
  main.cpp / CMakeLists.txt

tests/
  stage1/  18-01.xml ~ 18-30.xml + test.list    第一阶段 30 题（mis/err/ans 全 off）
  stage2/  18-01.xml ~ 18-30.xml + test.list    第二阶段 30 题（mis/err/ans 全 on）

scripts/            出题生成器 / 合规检查器 / 跑分工具（详见第四节）
docs/               技术报告与出题规范

> 说明：题目文件名的 `<18>` 是"抽签顺序"。正式提交时须按 `<抽签顺序>-<两位题目序号>.xml`
> 重命名（见第五节打包脚本）。
```

---

## 二、参赛程序编译与运行

编译（与平台同源构建，需 Boost；平台环境 Ubuntu 18.04 + gcc 7.5.0）：

```bash
g++ -O2 -std=c++11 -I include -o example example/*.cpp \
    lib/libframe.a lib/libutility.a -lboost_thread -lboost_chrono -lpthread
```

> 注：Boost ≥ 1.69 已移除 `libboost_system`，无需再链接；平台自带 `build/` 的 CMake 工程亦可直接构建。

运行（平台服务器 + 客户端两个终端）：

```bash
# 终端 1：启动平台服务器（-td 指定题目目录，-mode it|nt 切换指令语言/自然语言项目）
./cserver -td ../tests/stage1 -eval ../lib/libasp -log log -mode nt -test all

# 终端 2：运行参赛程序
./example
# 得分见 log/<队伍名>.log 的 `# Score:` 行
```

**注意事项**

- `res/iclingo` 是 32 位静态二进制，`cp` 后须 `chmod +x`，否则所有行动返回 false、全场 0 分；
- 端口残留会导致 `bind: Address already in use`，用 `pkill -x cserver` 清理（精确匹配，
  用 `-f cserver` 会误杀执行命令的 shell 自身）；
- 单题分数存在运行多态（同一二进制多次运行单题可差 ±35 分），比较方案效果须多轮取均值。

---

## 三、自出赛题遵循的规范

题目标准以 **《2026 中国机器人大赛服务机器人仿真项目出题指南》** 与
**《2026 年度赛事规则（服务机器人仿真项目）》** 为唯一依据，不参照其他来源。
要点摘录：

| 来源 | 条款 | 要求 |
|------|------|------|
| 指南 §二.1 | 阶段开关 | 第一阶段 `mis/err/ans` 均为 `off`，第二阶段均为 `on` |
| 指南 §二.1 | 编号 | `robot=0`、`human=1` 且唯一，编号自 0 起不断号，位置编号非负 |
| 指南 §二.2 / 附录A | 字段格式 | `sort` 居首；小物体 `sort,size,color,at\|inside`；大物体 `sort,size,at`；容器 `sort,size,at,type,opened\|closed`；同一行字段的物体 id 必须与 `sort` 一致；不可出现完全一样的大/小物体；一个位置至多一个大物体 |
| 指南 §二.3~§二.5 | `mis/err/extra` | 各段允许的字段类型、`err` 的 `r`(正确)/`w`(错误) 组合、`w` 不得与 `info` 矛盾、`extra` 每条须在 `instr` 的 `info` 中指出 |
| 指南 §三 / 附录B | 指令格式 | 逐条与附录B模板一致（条件集合与顺序）；`cons` 结尾四个括号、其他指令三个括号；单物体用 `X`、两物体 `X` 后 `Y`；`(:cons_notnot` 内层只能是 `(:info`；一条指令不能同时出现两个小物体；同一题不得重复 `task`/`cons` |
| 指南 §四 / 附录C | 自然语言 | 与 `instr` 逐句一一对应、每句以英文句号结尾；**`info`、`instr`、`nl` 三处凡涉及小物体都必须带颜色描述**（规则 §2.7 三(2)） |
| 指南 §五 / 规则 §2.5 | 分值 | 单题理论满分 = `40×目标数 + 20×约束数 − 行动扣分 + 效率分`，须落在 **200–1000**；`info` 句不计入目标/约束数 |
| 规则 §2.5 一 | 约束初始态 | 题目不得包含一开始就被破坏的约束 |

---

## 四、合规自查工具

`scripts/` 下为出题与自查工具，**提交前应全部通过**：

| 脚本 | 检查内容 |
|------|----------|
| `check_appendixB_2026.py` | 逐条指令与指南附录B模板比对（条件集合+顺序）、容器描述语法、阶段开关 |
| `check_syntax_2026.py` | XML 良构、各段括号平衡、附录A 字段顺序、指令结尾括号数、谓词白名单、X/Y 变量 |
| `check_rules_2026.py` | 编号/断号、字段完整性、重复物体、重复指令、理论满分上限、NL 句数与句号 |
| `check_cons_init.py` | 约束初始满足性（被破坏 = 题面缺陷） |
| `check_submit_2026.py` | NL 与指令逐句对应（附录C 句型）、NL 小物体颜色、同行字段 id 一致、理论满分核算 |
| `check_stage2_2026.py` | 第二阶段 `mis/err/extra` 三段规则、`r/w` 组合、`w` 与 `info` 一致性、`instr` 的 `info` 与真实环境一致 |
| `run_validate.sh` | 调用官方 validator 批量校验（语法 + ASP 可解性），判据为"真 UNSAT"(Execution failed) |
| `gen_tests_v2.py` | 权威出题生成器（30 模板 → 约束初始态修复/冲突改写/理论满分抬升 → 输出两阶段 60 题） |

**一键终检**（提交前跑一遍）：

```bash
bash scripts/robocup-终检.sh tests/stage1 tests/stage2
```

---

## 五、提交包生成

按赛事规则 §2.7 二：题目以压缩包提交、主文件夹统一命名为
`<抽签顺序>-<学校>-<队伍名称>`，内含代码与题目两个压缩包；题目文件命名格式为
`<抽签顺序>-<两位题目序号>.xml`。

```bash
bash scripts/robocup-打包.sh <抽签顺序> <学校> <队伍名称> <stage1|stage2>
# 例：bash scripts/robocup-打包.sh 7 重庆科技大学 Dawnluis stage2
```

生成的包结构：

```
7-重庆科技大学-Dawnluis/
  ├─ example.zip   内含 example/ 与参赛代码源码
  └─ tests.zip     内含 tests/ 与 7-01.xml ~ 7-30.xml
```

---

## 六、实机基线（本机平台，自出题，NT 模式）

| 数据集 | 得分 | 说明 |
|--------|------|------|
| 平台自带 NT stage1（48 题） | ≈8058 | 与平台官方题库同带 |
| 自出 stage1（30 题） | ≈6224 | 本轮定稿版本 |
| 自出 stage2（30 题） | ≈5578 | 两轮均值（旧方案 ≈5191） |

---

## 七、文档

- `docs/技术报告-20260904.md` —— 参赛程序（客户端）的技术分析与优化记录
- `docs/技术报告-20261016.md` —— 赛题出题整改与合规检查体系（含第二阶段信息组织方案的实机对比）
- `docs/2026出题规范与自查清单.md` —— 出题规范逐条清单与检查项对照