# 赛前现场清单 · RoboCup 服务机器人仿真（队伍 Dawnluis）

> 代码与题目已定稿：GitHub `DawnLuis/robocup-home-robot`，HEAD `e86d2c6`。
> 自出题 stage1=6462 / stage2=5917（NT 模式，多轮均值）。现场按下面顺序打勾执行。

---

## 一、报到当天（适应性调试，每台主机 10 分钟 × 2）

- [ ] 把 `example/` 放进平台工程目录，确认**能编译、能运行**
      ```
      g++ -O2 -std=c++11 -I include -o example example/*.cpp \
          lib/libframe.a lib/libutility.a -lboost_thread -lboost_chrono -lpthread
      ```
      （此编译方式**已在本机对 2025 与 2026 两个官方平台验证通过**：2026 平台自出 stage1
      跑出 6464，与 2025 逐题对比仅 3 题各 +2，零回归）
- [ ] 若改用平台的 CMake 工程：**2026 包顶层**写的是 `CMAKE_MINIMUM_REQUIRED(VERSION 2.6.0)` ——
      在比赛环境（Ubuntu 18.04 + CMake 3.10）正常；若在你本机的新版 CMake（≥4.0）上配置会报错，
      加参数 `-DCMAKE_POLICY_VERSION_MINIMUM=3.5` 即可（与比赛无关，是平台包的老声明问题）
- [ ] **`chmod +x res/iclingo`** ← 32 位静态二进制，拷过去常丢执行权限，
      丢了会**全部行动返回 false、全场 0 分**（血泪教训，必查）
- [ ] 跑一遍自出题确认得分正常：
      ```
      bash scripts/run_suite.sh <平台目录>/tests/stage1 s1check 1
      bash scripts/run_suite.sh <平台目录>/tests/stage2 s2check 1
      ```
- [ ] 端口残留清理用 `pkill -x cserver`（**精确匹配**，用 `-f cserver` 会把自己杀掉）

## 二、比赛当天上午（提交，过时视为放弃资格）

- [ ] **拿到抽签顺序 X**（这是所有命名的基础，没有它不能出包）
- [ ] 复核题目（应全部为 0）：
      ```
      bash ~/Downloads/robocup-终检.sh ~/Downloads/stage1-submit-2026 ~/Downloads/stage2-submit-2026
      ```
- [ ] 生成两个阶段的提交包：
      ```
      bash ~/Downloads/robocup-打包.sh X 重庆科技大学 Dawnluis stage1
      bash ~/Downloads/robocup-打包.sh X 重庆科技大学 Dawnluis stage2
      ```
- [ ] 核对包结构（与上次提交被接受的包一致）：
      ```
      X-重庆科技大学-Dawnluis/
        ├─ example.zip   内含 example/ 与参赛代码源码
        └─ tests.zip     内含 tests/ 与 X-01.xml ~ X-30.xml
      ```
- [ ] 确认题目文件名为 `X-01.xml`~`X-30.xml`（**不是** `18-01.xml` —— 18 是上次的抽签顺序）

## 三、审题阶段（裁判与各队审题后有 30 分钟自我调试时间）

- [ ] 用终检脚本再扫一遍全部题目
- [ ] 重点复核第一阶段实际踩过的两条（现已修好，但要确认没回退）：
      · **阶段开关**：第一阶段 `mis/err/ans` 必须全是 `off`
      · **容器字段序**：`(sort)(size)(at)(type N container)(opened|closed)`
- [ ] 对题目有异议当场提出（规则允许向技术委员会申请查看 log）

## 四、比赛进行中

- [ ] 每题得分看 `log/Dawnluis.log` 的 `# Score:` 行
- [ ] 出现卡顿先等 1 分钟，仍未解决由操作手跳过（该题记 0 分）
- [ ] **不要中途改代码** —— 代码是上午一次性提交、两阶段共用同一份二进制；
      改了就没人验证过了（任何临时改动都可能引入比它修掉的问题更大的问题）

## 五、已知的分数特性（遇到时不要误判）

- 第二阶段单题分数**天然波动 ±35 分**（`ans=on` 时 AskLoc 每题重新掷骰子），
  同一份代码连跑两次总分可差 ±100 —— 属正常，不是故障
- 阶段一总分极稳（自出题三轮 6458/6462/6462）

## 六、备用命令速查

| 用途 | 命令 |
|------|------|
| 跑分（多轮） | `bash scripts/run_suite.sh <题目目录> <标签> <轮数>` |
| 逐题打表 | `awk '/^<[0-9].*\.xml>/{t=$0;gsub(/[<>]/,"",t)} /^# Score:/{print t,$3}' log/Dawnluis.log` |
| 题目终检 | `bash scripts/robocup-终检.sh <stage1目录> [stage2目录]` |
| 出提交包 | `bash scripts/robocup-打包.sh <抽签顺序> <学校> <队伍名称> <stage1\|stage2>` |
| 官方 validator | `TO_MS=30000 bash scripts/run_validate.sh <题目目录> <标签>` |
| 单题诊断 | 建目录放单个 xml + `test.list`，`cserver -td <目录>` 秒级单跑 |