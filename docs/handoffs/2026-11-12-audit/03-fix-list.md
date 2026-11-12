# 03 修改与修复清单（2026-11-12）

每一项都写明：解决哪条发现、改哪里、怎么改、怎么验收、有什么坑。发现编号见
[01-audit-report.md](01-audit-report.md)，决定编号（OD-A 到 OD-H）见
[02-blueprint-v2.md](02-blueprint-v2.md) 第 9 节，排期和并行方式见
[04-development-plan.md](04-development-plan.md)。

行号对应基线提交 `e8c8a95cd9fea90db02518879e7d30931b5f6926`。动手前先确认行号还对得上；对不上
就以符号名为准。

## 0. 对所有条目都适用的规矩

1. **冻结的东西不动。** 四个闸门阈值（离散不超过 6 美分、最差变体至少 4 美分、净边际至少 5 美分、
   流动性至少 5,000 美元）、十变体的集合与顺序、`selfcheck` 的 10 项检查、
   `tests/fixtures/papersim/` 下的四份回归夹具（`regression_*.json`）和一份 FotMob 摘录夹具，
   一律不改。新功能以"新增函数"的方式加在旁边。
2. **已有迁移不改、不删、不重放。** 新的表结构变化一律写成新的迁移文件，同时更新
   `database/migrations.lock.json` 和两处迁移计数：`tests/test_project_postgres.py:82` 和
   `tests/test_research_dispatch.py:351`（现在都是 70）。漏掉任何一处，全量测试都会失败。
3. **改文档或工作流之前，先找出读它的测试。** 34 个测试文件引用 `README.md`；3 个测试直接读取
   `AGENTS.md`（`tests/test_codex_node_push_policy_rules.py`、
   `tests/test_project_database_persistence_rules.py`、`tests/test_phase1_docs_required_terms.py`）；
   `tests/test_native_postgres_workflow.py` 读工作流文件，其中第 191 行断言工作流里一条提到
   `DELIVERY_PLAN.md` 的注释。没有测试读取 `DELIVERY_PLAN.md` 的内容。动手前用
   `grep -l "<文件名>" tests/*.py` 再找一遍，同一个节点里一起改。不允许为了让改动通过而删测试。
4. **三个守卫测试**（蓝图 8.6）：`tests/test_phase1_live_surface_guard.py`（标识符黑名单）、
   `tests/test_database_persistence_iron_rule.py`（冻结的数据库连接模块白名单）、
   `tests/test_supabase_durable_only_scope.py`（迁移文件里禁止网址和连接串）。它们是铁律的守卫；
   需要改它们的白名单时，在节点计划里写明并经复审，不能顺手改。
5. **每个节点走完整流程**：聚焦测试、全量离线验证
   （`.venv/bin/python scripts/verify_local.py --full`）、`git diff --check`、编译检查、秘密扫描、
   聚焦的本地提交、独立只读复审并给出 `VERDICT: PASS`，然后才推送（`AGENTS.md` 的推送策略）。
   CodeGraph 同步按 2026-09-12 的授权可以不做；做没做，如实记录。
6. **纸面边界不变。** 任何条目都不引入账户认证、私钥、签名或下单；新表沿用仓库惯例的
   `paper_only / report_only / readonly` 三列并加 `CHECK`。
7. **对线上账本数据库只做三类操作**：只读查询、新增对象（表、视图、列）、插入。不对已有的
   `decisions / resolutions / bankroll` 行做 `UPDATE` 或 `DELETE`。唯一的例外是 FX-02 对两个
   已有视图的替换，它需要 OD-H 的肯定答复。
8. **不要执行已作废的 11-11 交接里的任何条目**，特别是不要改 `tools/analysis/codequality.py`。

"计划记录"在下文多次出现，指蓝图 8.1 说的记录位置：默认是 `DELIVERY_PLAN.md` 的新小节。

## 1. 第一组：让数字可信（里程碑 M0）

### FX-01 账本盈亏改为扣费后口径 ｜P1｜对应 P-2

**现状**：`src/polymarket_alpha_lab/papersim/ledger.py:211-259` 的 `settle_natural`、`settle_exit`
都是 `pnl = proceeds - stake`。

**改法**

1. `PaperSettlement`（`ledger.py:162`）在现有三个字段之后追加带默认值的字段
   `fee_total: float = 0.0`，并加只读属性 `pnl_net`，返回 `pnl - fee_total`。现有的 `pnl` 保持
   毛口径的含义不变，这样已有锚点和测试逐字节不变。
2. `settle_natural` 增加仅限关键字的可选参数 `fee_rate: float | None = None`。给了费率时：
   份数 = `stake / price`，入场费 = 份数 × 费率 × `price` × (1 − `price`)，化简即
   `stake × 费率 × (1 − price)`；写入 `fee_total`。自然结算没有离场费。
3. `settle_exit` 增加 `fee_rate` 和 `exit_fee_rate` 两个可选参数。离场费 = 份数 × 离场费率 ×
   `exit_price` × (1 − `exit_price`)；`fee_total` 是入场费与离场费之和。
4. 费率一律从 FX-06 的费率表取，不在这里写数字。
5. 新增一个只读报告脚本 `tools/papersim_ledger_report.py`：读一份账本导出（JSON）或用只读
   `SELECT` 读数据库，按队列输出毛、净两套回报率。它是 FX-11 评估模块的最小前身，FX-11 完成后
   并入。

**验收**

- 手算用例进测试：250 美元、成交价 0.56、体育费率 0.05。份数 446.4286，入场费
  250 × 0.05 × 0.44 = 5.50。赢：毛盈亏 +196.43，净 +190.93。输：毛 −250.00，净 −255.50。
- 离场用例：400 美元、成交价 0.69、离场价 0.585、两端费率 0.05。份数 579.7101，入场费
  400 × 0.05 × 0.31 = 6.20，离场费 579.7101 × 0.05 × 0.585 × 0.415 = 7.04，毛盈亏 −60.87，
  净 −74.11。（账本里这一笔按 580 份整数记账，毛盈亏是 −60.70；这里按精确份数算，两者都对，
  测试里用精确份数。）
- 对 `docs/paper-sim/review-2026-10-30/settled_ledger.json` 运行报告脚本：毛回报率必须复现
  23.30%（本金 10,954.36，盈亏 2,552.43）；净回报率应落在 20% 到 21% 之间（确切值取决于每个市场
  归入哪个费率类别，把归类表一并输出）。
- `python -m polymarket_alpha_lab.papersim.cli selfcheck` 仍是 10/10，输出与修改前逐字节相同。

**注意**：历史市场当时是否收费、按哪档收，无法从仓库核实。报告里把历史净值标为"按
2026-11-12 费率表回推的估算"，不要当成会计数字。

### FX-02 核对并修复业绩视图的重复计账 ｜P1｜对应 P-3｜替换视图需要 OD-H

**这是服务器上的操作，分两段。** 前一段全是只读的，现在就做；后一段要替换数据库里的两个视图，
需要你对 OD-H 选 ①。

为什么把"应用"单列为一项决定：这个修复已登记为 `DELIVERY_PLAN.md` 第 73 节的前置项（P4-0a），
但那一节同时写着"新迁移须单独审查应用"；账本数据库不在仓库迁移台账的管理之下；`AGENTS.md`
还规定不自动改动已有的安装。所以不把它当成默认授权。

**只读段（不需要任何决定）**

1. 确认目标：`PAPERSIM_PG_DSN` 指向的 `paper_sim` 数据库。顺带回答核实项 V-9。
2. 读现状：`select pg_get_viewdef('public.model_performance'::regclass, true);`，对
   `forecast_calibration` 同样读一次。与 `ledger.ddl()` 的文本和修复迁移的文本对比，记录三种
   可能之一：已是修复后版本、是原始版本、两者都不是。
3. 把账本三张表导出为 JSON，留在服务器的私有目录并登记校验值。用 FX-01 的报告脚本在库外算出
   修正后的数字：每个市场的盈亏按份数分摊到它的各笔入场（与修复迁移的口径相同），再扣费。
   这样即使不动数据库，你也能拿到正确的数字。
4. 导出要不要进仓库：`DELIVERY_PLAN.md:79-80` 规定 GitHub 只放已审阅的脱敏摘要，而 10-30
   评审包是一个已有的先例。按先例办——字段范围与 10-30 那份相同，`reason`、`evidence` 这类
   自由文本逐条审阅后再放进 `docs/paper-sim/ledger-snapshots/<日期>/`。如果你不希望明细进仓库，
   就只提交报告。

**替换段（需要 OD-H 选 ①）**

5. 备份：对三张表和两个视图做逻辑备份，放在服务器上的私有目录，不进仓库。
6. 跑只读夹具测试 `tests/test_papersim_perf_view_fix.py`（需要 `WP_P4_READONLY_PG=1`，具体环境
   变量以该测试文件头部说明为准）。9 项全过才继续。
7. 在一个事务里执行 `supabase/migrations/20261107000000_papersim_perf_view_fix.sql`。如果
   `forecast_calibration` 还缺 NO-basket 那一个条件（`ledger.py:302-305` 提到的那一行），按
   `ledger.ddl()` 里的视图定义一并替换。只替换视图，不碰任何数据行。
8. 回读并留证：修改前后各导出一次两个视图的全部行。`crypto_touch` 的 `total_pnl` 应当减少
   1,305.20（11-07 时是从 2,795.00 到 1,489.80；之后如果有新的结算，绝对值会不同）；各类型的
   计数列不应变化。
9. 记录：在计划记录里写明执行时间、所执行 SQL 文件的 SHA-256、前后对比、备份的校验值。如果
   V-9 的答案是这个数据库有自己的迁移台账，就通过台账应用并记下台账条目。

**验收**：只读段——视图现状的结论、修正后的数字、导出的校验值都在计划记录里。替换段——再加上
修改前后的视图行、测试输出、备份的校验值。

### FX-03 把服务器上的决策代码和证据收进仓库，并建立运行版本签到 ｜P1｜对应 P-1、G-5

**目的**：第一步只求"看得见"——把现在实际在跑的东西原样收进来，不改它。真正用库代码替换它是
FX-15、FX-16 的事。

**步骤**

1. 清点：列出服务器 `~/paper-sim` 下全部文件及大小，分成四类——代码（`.py`、`.sh`、`.sql`）、
   报告和小型结果（`.md`、小的 `.json`）、数据快照（大的 `.json`）、缓存与凭据类。
2. 收进仓库的位置：`docs/paper-sim/server-mirror/<日期>/`，保持原目录结构。放在 `docs/` 下是
   有意的：它是存档，不是可导入的包，也不会碰到检查仓库顶层结构的测试。
3. 排除：任何凭据、`.env`、密码文件、`~/pal-artifacts`、数据库文件、缓存。
4. 大于 1 MB 的文件不进仓库，只在清单里记录路径、字节数和 SHA-256。
5. 提交前做秘密扫描和服务器地址扫描；命中的逐个处理。
6. 写清单 `MANIFEST.json`：每个文件的路径、字节数、SHA-256；服务器上库代码检出的
   `git rev-parse HEAD`；`git status --porcelain` 的行数；Python 版本；清点时间。
7. 写一张"替换对照表"进计划记录：每个仍在使用的服务器脚本做什么、对应库里哪个函数、
   库里缺什么。这张表就是 FX-10、FX-15、FX-16 的需求清单。
8. 立规矩并执行：从这一天起，每次扫描开始时把库代码的提交号和工作区是否干净记下来（在账本 v2
   落地之前，先记在该轮的输出文件里并同步进仓库）。

**验收**：清单入库；扫描无命中；对照表覆盖所有仍在使用的脚本；最近一次扫描有版本记录。

**注意**：`tests/test_phase1_no_review_scratch_references.py` 会扫描 `docs/` 下的所有文本文件，
禁止出现以 `.review/` 开头的路径和三个特定的草稿文件名。镜像进来的文件如果命中，改写该行的
路径表述，不要改测试。

### FX-04 跨联赛胜负盘的接线证明 ｜P1，期限 11-24 之前｜对应 P-1、OD-F

1. 在 FX-03 收进来的当前扫描脚本里查找 `check_cross_league_mw`、`CROSS_LEAGUE_ML_CLASS`、
   `bridge=` 的调用，记录文件和行号。
2. 找到了：在计划记录里记下证据（文件、行号、提交号），状态板标"已接线"。
3. 没找到：状态板把"足球·胜负盘·跨联赛"队列标为"冻结（接线未证明）"，11-24 不恢复入场。
   等 FX-08 的总入口上线后自动满足，届时再解冻。

**验收**：状态板上这个队列的状态有明确依据，二者必居其一。

### FX-05 状态板和过期文字 ｜P1｜对应 G-1、G-2、G-3

**改法**

1. `DELIVERY_PLAN.md`：在标题之后、现有第 1 节之前插入"状态板"一节，不超过一页，内容按蓝图
   第 8.1 节：三条线各自的里程碑、下一步、在等谁；八项待决事项及其当前答复。原有内容全部保留。
2. 在文末追加第 76 节，记录本次审核、蓝图 v2 的采纳情况和各项决定的答复。
3. 过期状态用"追加更正"的方式处理，不改写原文：
   - 第 69 节 WP-P1 的"PENDING……不推送"下面加一行带日期的更正，写明评审三轮已完成、已推送，
     并给出提交号。
   - 第 73 节 P4-0b 写明现状：是被 WP-P5 的严格时序重做取代，还是仍然欠着。由协调者根据服务器
     上的证据判断后落笔。
4. `docs/paper-sim/usage.md:123`、`:185` 和
   `src/polymarket_alpha_lab/papersim/soccer_model.py:12-26`：把"跨联赛胜负盘 BANNED"改成与
   `gates.py:162` 一致的现状（有条件参与：必须有桥、最差变体至少 5 美分、固定 150 美元）。
   `usage.md:137` 的荷甲"尚未验证"改为已验证并引用第 71 节。
5. `README.md` 顶部加不超过十行：指向状态板，说明当前主线是模拟盘。
6. 记录位置按蓝图 8.1：默认仍是 `DELIVERY_PLAN.md` 的新小节。只有 OD-E 选了 ①，才新建
   `docs/plan/` 下的三个分线记录文件。

**验收**：引用 `README.md` 的 34 个测试文件全部通过；`tests/test_native_postgres_workflow.py`
通过（不要动工作流里提到 `DELIVERY_PLAN.md` 的那条注释）；一个没读过项目的人只看状态板，能
回答"现在几条线、各到哪、等谁"。

**不在这一条里做**：`AGENTS.md` 的改动放在 FX-25，等 OD-E。

### FX-06 按类别的费率表 ｜P2｜对应 P-7

**新增** `src/polymarket_alpha_lab/papersim/fees.py`（纯函数，无输入输出）：

- 常量 `FEE_SCHEDULE_AS_OF = "2026-11-12"`、`FEE_SCHEDULE_SOURCE`（官方文档地址）。
- 只读映射 `TAKER_FEE_RATES`，数值取自官方文档 2026-11-12 的版本：

  | 类别 | 吃单费率 |
  | --- | ---: |
  | crypto | 0.07 |
  | sports | 0.05 |
  | finance | 0.04 |
  | politics | 0.04 |
  | economics | 0.05 |
  | culture | 0.05 |
  | weather | 0.05 |
  | other | 0.05 |
  | mentions | 0.04 |
  | tech | 0.04 |
  | geopolitics | 0 |
  | combos | 0.05 |

- `taker_fee_rate(category)`：类别不认识就抛 `ValueError`，不默认成体育费率。
- `entry_fee(stake, price, rate)`、`exit_fee(shares, exit_price, rate)`、`fee_per_share(price, rate)`。
  后者与 `gates.fee_cost` 等价，加一条测试钉住两者相等。
- 如果从官方接口拿到的市场元数据里带有该市场自己的费率参数，以它为准并记录；与表不一致时拒绝
  该候选并报警——说明费率表该更新了。

**同时**：`gates.py:98-99` 的两个常量保留，加测试断言它们等于表里的值；`gates.py:364` 的注释（以及
`:38`、`:92` 两处相同的表述）把"notional"改成"份数 C"。`evaluate_candidate` 的签名和默认值不动（冻结接口），新的总入口
（FX-08）强制要求显式给出类别。

**验收**：每个类别一条测试；未知类别抛错；表是只读的；实现前重新读一次官方文档，数值有变化就
先更新表和日期。

### FX-07 让真实数据库的 CI 跑起来 ｜P2｜对应 R-2

**改法**（`.github/workflows/native-postgres.yml:2-4` 的 `on:` 段）

1. 保留 `workflow_dispatch` 和现有的 `pull_request`。
2. 增加 `push` 到 `main` 的触发，路径限定为：`supabase/migrations/**`、`database/**`、
   `src/polymarket_alpha_lab/project_postgres/**`、`src/polymarket_alpha_lab/*_psycopg.py`、
   `src/polymarket_alpha_lab/papersim/**`、`tests/test_project_postgres*`、`tests/test_papersim_*`、
   以及工作流文件自身。
3. 增加每周一次的 `schedule`。不要每天跑：三个分区加起来一次要几十分钟，私有仓库的分钟数有
   限额。
4. 增加第四个分区 `papersim`，跑 `tests/test_papersim_ledger.py` 的集成测试和
   `tests/test_papersim_perf_view_fix.py`。它们需要一个一次性的本机数据库和相应的环境变量
   （`PAPERSIM_PG_DSN`、`WP_P4_READONLY_PG=1` 等，以两个测试文件头部的说明为准），用工作流里
   已经组装好的 PG18 前缀临时初始化一个即可，不使用任何已安装的集群、角色或密码。
5. `tests/test_native_postgres_workflow.py` 读这个工作流文件，同步更新。

**验收**：先用手动触发跑通一次，记录运行编号；之后一次涉及迁移的推送自动触发并通过。

### FX-13 加密"到期价"市场的方向显式化 ｜P2｜对应 P-8

**改法**（`src/polymarket_alpha_lab/papersim/crypto_model.py`，只新增）

- 新增 `terminal_yes_probability(prob, *, yes_when)`：`yes_when` 只接受 `"below"` 或 `"above"`；
  `"below"` 原样返回两个约定的概率，`"above"` 返回各自的补。
- 新增 `conservative_edges_for_terminal(prob, *, yes_when, yes_ask, no_ask)`，内部先做方向转换
  再套用现有的保守取值规则。
- 现有的 `conservative_edges`（`:274`）不改行为，只在文档字符串里注明：到期价市场请用新函数。
- 总入口（FX-08）和今后的扫描代码只允许用新函数处理到期价市场。

**验收**：对同一个障碍价，`above` 的 YES 边际等于 `below` 的 NO 边际在对称报价下的镜像；
`yes_when` 给别的值抛错；触价锚点（`selfcheck` 的三个加密锚点）不变。

### FX-14 "冻结"常量改成只读 ｜P3｜对应 P-11

- `gates.py:74` 的 `GATES`、`gates.py:161` 的 `SUSPENSION_REGISTRY`、`crypto_model.py:47` 的
  `VOL_WINDOW_BARS`：用 `types.MappingProxyType` 包一层，做法与 `league_strength.py` 的 κ 表相同。
- 动手前 `grep -n "GATES\[" -r tests src` 和 `grep -n "monkeypatch" tests/test_papersim_*.py`，
  确认没有测试靠改写它们来工作；有的话改成传参或局部替身。
- 顺手修 `tests/test_papersim_gates.py:847`：把 `match="qs_variants\[1\]"` 改成原始字符串
  `match=r"qs_variants\[1\]"`。

**验收**：对三个映射赋值抛 `TypeError`；`selfcheck` 10/10；CI 日志里不再有 `SyntaxWarning`。

**顺序**：FX-22 里"出现 `SyntaxWarning` 即失败"的配置，必须等这里把第 847 行修好并合并之后
才能合并，否则全量测试会失败。

## 2. 第二组：证据底座（里程碑 M1）

### FX-08 一个总入口 `decide_entry` ｜P1｜对应 P-1、P-13

**新增** `src/polymarket_alpha_lab/papersim/pipeline.py`（纯计算，无输入输出）。

**输入**

- 模型报价（现有的 `SoccerCandidate` 或等价的映射）和订单簿档位；
- 市场上下文：市场与代币标识、市场类型、费率类别、是否跨联赛、是否带桥、所属比赛、方向标签；
- 组合状态：资金、现金、已预留、同一场比赛已持有的方向、所属团队已占用额度与上限；
- 新闻核对结果、低进球风险标记或用于计算它的原料、阵容确认度；
- 订单簿的取数时间、当前时间、允许的最大时效。

**按顺序做的检查**（任何一步不过都记录原因；全部原因都要收集，不在第一个失败处返回）

1. 订单簿时效：超过允许时效直接拒绝，原因 `stale_book`。
2. `gates.suspension_policy`：`eligible` 为假则拒绝。
3. `gates.evaluate_candidate`，费率用 `fees.taker_fee_rate(类别)`，不允许省略。
4. `gates.check_cross_league_mw`，用上一步得到的最差变体边际。
5. `risk_policy.held_fixture_add_allowed`。
6. `risk_policy.sizing_tier` 和 `tier_notional`：跨联赛胜负盘用 `CROSS_LEAGUE_ML_CLASS`，国内
   胜负盘用 `DOMESTIC_ML_CLASS`，其余用标准档。
7. 下注额不得超过验收行走的金额（现在是 250 美元）；团队额度；`bankroll_available` 不小于下注额。

**输出** `EntryDecision`：是否接受、全部原因、各步的原始结果、下注额、费率、入场费、
闸门版本字符串（例如 `gates-2026-11-07+fees-2026-11-12`，用来划分队列）。

**约束**：不改任何现有函数；新代码只是把它们按固定顺序串起来。

**验收**

- 现有锚点穿过总入口后数字不变：#48（布伦特福德对森林，大 2.5）接受；BOU-LEE 因离散 6.09 美分
  拒绝；HOF-LYO 不带桥时拒绝。
- 每一种拒绝原因至少一条测试；任何子检查不过，总结论必为拒绝（用穷举或性质测试证明）。
- 跨联赛胜负盘：不带桥拒绝；最差变体 4.9 美分拒绝；通过时下注额恒为 150 美元。

### FX-09 账本 v2、存储适配和历史导入 ｜P1｜对应 P-6、P-3、P-4｜需要 OD-D

表的清单和原则见蓝图第 6 节。这里补充实现约束。

1. **建在哪里**：先回答核实项 V-9。原则是 `papersim` 模式由仓库的迁移台账管理，不再手工改表。
2. **迁移**：一个新文件创建 `papersim` 模式和七张表。必填列加 `NOT NULL`；价格加
   `CHECK (price > 0 AND price < 1)`；下注额加 `CHECK (stake > 0)`；`entries.candidate_id` 唯一；
   外键齐全；三列边界标记带 `CHECK`。
3. **只增不改**：对 `entries`、`settlements`、`bankroll_events` 加触发器，`UPDATE` 和 `DELETE`
   一律报错。更正用追加一条冲销记录的方式表达。
4. **存储代码**：`papersim/store.py`（纯的行与对象转换）和 `papersim/store_psycopg.py`（连接与
   事务），照现有 `*_store.py` 加 `*_psycopg.py` 的写法：连接串先过
   `validate_local_postgres_dsn`，SQL 全部参数化，一次扫描的候选和入场在同一个事务里写入。
5. **补全** `ledger.py:94-110` 的 `record_entry` 和 `mark_to_market`，并同步改写钉住它们
   "未实现"状态的测试。
6. **历史导入**：一个可重复执行的脚本，把现有 `decisions / resolutions / bankroll` 的行映射进
   新表，保留原编号；同一市场多次入场的，按份数把市场级盈亏分摊到各笔（与修复迁移的口径相同）；
   缺失的出处字段留空并标注"历史导入"。导入不修改旧表。
7. **视图**：按队列的毛、净业绩；校准；集中度。旧的两个视图保留。

**验收**

- 在一次性的测试数据库上：建表、写一次完整扫描、读回、导入历史、三个视图有数。
- 导入后的净盈亏合计 = 旧表毛盈亏合计 − 回推费用合计，分币不差。
- 市场 3866000 的两笔入场各自有结算行，合计 1,305.20。
- 对 `entries` 执行 `UPDATE` 报错。
- 这些测试进 FX-07 的 `papersim` 分区。

**三个要先知道的守卫**

- 迁移计数有两处（第 0 节第 2 条），都要更新。
- `tests/test_database_persistence_iron_rule.py` 第 706 行起有一份冻结的"允许打开数据库连接的
  模块"白名单。`papersim/store_psycopg.py` 必须显式加进去。这是铁律 1 的守卫，属于 OD-D 批准的
  范围；在节点计划里写明，并经复审。
- `tests/test_supabase_durable_only_scope.py:44-59` 禁止迁移文件里出现网址和连接串，注释里也
  不要写。

**OD-D 选了 ② 时的降级做法**：不建新表；只加一个新迁移，给 `decisions` 加 `fee_rate`、
`entry_fee`、`code_commit`、`gate_report` 四个可空列，加一张 `rejected_candidates` 表，加净口径
视图。能解决 P-2 和一部分 P-4，解决不了 P-3 的根因。

### FX-10 补全各类市场的候选构造 ｜P1｜对应 P-1

**现状**：`soccer_model.py:430` 的 `candidate_from_variants` 只会构造大小球的"大"。

**改法**（只新增，现有函数逐字节不变）

- 新增一个通用构造函数，参数里显式给出市场类型和方向：大小球（大、小）、两队进球（是、否）、
  球队总进球（主或客，大、小）、胜负盘（主胜、平、客胜，各自的是与否）。让球只产出报价，入场由
  闸门的注册表拒绝。
- 每个变体的报价直接取自现有的概率函数：`over_probability`、`both_teams_to_score`、
  `team_total_over`、`MatchOutputs` 的 `home_win / draw / away_win`、`cover_probability`。
- 反方向用 1 减正方向。只接受半球盘口（盘口乘 2 为奇数）；整数盘口有走盘，遇到就抛错，不静默
  处理。
- 胜负盘三个结果各自取十变体中位数后加起来不一定等于 1（WP-P4 报告里是 0.988 到 1.005），这是
  现有口径，保持不变并在文档字符串里写明。

**验收**：对冻结夹具里的四场比赛，新函数构造的"大 2.5"与旧函数逐位相等；每种新类型有一条手算
或交叉核对的测试；`selfcheck` 在原有 10 项之外追加新项，原 10 项输出不变。

### FX-11 评估模块和晋级标准 ｜P1｜对应 P-4、P-5｜晋级数字需要 OD-G

**新增** `src/polymarket_alpha_lab/papersim/evaluation.py`（纯计算）和 `papersim.cli` 的只读
子命令 `evaluate`。

- 输入：入场与结算记录、标记价与收盘价、该队列全部候选的模型概率和市场中间价。
- 按队列输出：计数；毛、净回报率及区间（按比赛或按日分组的自助法，固定随机种子）；收盘价偏离的
  均值和区间；命中率对平均成交价；模型和市场各自的 Brier 与对数损失、配对差值的区间；分桶校准；
  盈利最多的一个市场占总盈亏的比例；最大回撤；晋级标准 A 到 F 逐条的通过与否和原因。
- 评分计算复用 `research_probability_scores.py`，不要再写第五套。它用 `Decimal`，在入口处转换
  即可。
- 指标的计算不依赖任何决定，可以先做。
- 晋级标准和暂停规则写成一份带版本号的常量，与蓝图 5.3 一致；它们只有在 OD-G 批准之后才启用，
  在那之前报告里只列指标、不下"通过或不通过"的结论。启用之后改动它等同于改冻结阈值，需要你批准。

**验收**：对 10-30 快照，输出与 `evidence/ledger_stats_output.txt` 中的确定性数字一致——回报率
23.30%、最大一个市场占比 51.1%、去掉它之后 12.22%、Brier 0.1873 对 0.2082；自助法区间允许
±1.5 个百分点的差异（重采样方式不同）。

### FX-12 输入快照登记和决定重放 ｜P2｜对应 P-6，闸门 0｜存放方式取决于 OD-E

- 每份输入文件在使用前登记：算 SHA-256，写入 `snapshots`。候选记录里引用它。
- 重放命令：给定候选编号，按记录取回快照（校验值不符即失败）、订单簿和参数，在记录的代码提交上
  重算，与入库的闸门报告逐字段比较。
- 快照文件设为只读，不覆盖；新版本是新文件、新校验值。"最新"指针单独存，不改旧文件。

**验收**：测试扫描产生的每个候选都能重放出相同结果；篡改快照一个字节，重放报校验值不符。

## 3. 第三组：把运行闭环搬进仓库（里程碑 M2）

### FX-15 数据适配器入库 ｜P1｜对应 P-1、P-12

- 位置：`src/polymarket_alpha_lab/papersim/adapters/`。
- Polymarket：只用官方公共接口（Gamma 取市场与事件，CLOB 取订单簿），复用仓库里已有的客户端
  （`api.py`、`team_research_gamma.py`）和 `public_http.read_public_body`。
- 行情：BTC、ETH 的 6 小时 K 线，只用完整的 K 线算波动率。仓库已有 Coinbase、Kraken 的读取器；
  结算口径以合约写明的来源为准，服务器现在用哪个来源以 FX-03 的清点为准。
- Understat 抓取器从服务器镜像迁入；`fotmob.py`、`espn_nba.py` 的读取改用有界读取，行为不变。
- 所有联网函数必须由调用方显式允许（沿用 V1 的 `--allow-public-fetch` 做法）；测试只用录制的
  响应，不联网。

**验收**：每个适配器有离线夹具测试；CI 不产生任何网络访问；FX-03 对照表里"取数"一栏全部有了
库内对应。

### FX-16 定时扫描、标记价采集、结算 ｜P1｜对应 P-1、P-5

`papersim.cli` 新增四个子命令，全部是"跑一次就退出"，由定时任务调度，不做常驻进程：

| 子命令 | 做什么 | 边界 |
| --- | --- | --- |
| `run-scan` | 取数、登记快照、算模型、对每个候选调用 `decide_entry`、把全部候选和被接受的入场写库 | 有请求数上限、市场数上限和截止时间；到点停，不延长；工作区不干净就拒绝运行 |
| `capture-marks` | 给未平仓的入场和本队列的全部候选记录买卖价；体育类在开赛前固定时刻的那一条标记为收盘价 | 只读公共接口 |
| `settle` | 从官方接口读已结算市场的结果，写结算行（扣费） | 结果明确的自动写；有争议、取消、五五开的进入人工确认队列，不默认判负 |
| `report` | 当日持仓、净盈亏、现金恒等式、数据时效告警 | 只读 |

人工确认队列复用 V1 的结算确认模块的做法，不新造。

**退役服务器脚本**：四个子命令稳定后，服务器的定时任务只调用仓库在某个固定提交上的这些命令；
逐轮脚本归档到镜像目录，不再运行。

**验收**：连续 7 天无人值守运行；期间没有手工改库；每天现金恒等式通过；任取 5 个候选都能重放。
之后进入晋级标准 F 条的 30 天计时。

### FX-17 跨联赛胜负盘的暂停规则 ｜P2｜对应 P-9｜需要 OD-G

在现有做法（固定 150 美元、累计 20 笔再议）之上，预先写死：

- 结算满 10 笔后，如果该队列净盈亏低于 −600 美元（4 个单位），暂停新入场并复核；
- 入场满 20 笔后，如果收盘价偏离均值的 95% 区间上界小于 0，暂停新入场并复核；
- κ 表只在每个赛季开始前重新冻结一次，赛季中不改。

第一条的含义是"暂停并复核"，不是"判定无效"：在没有任何优势、赔率五五开的情况下，10 笔里
输到 4 个单位的概率也有约 17%。

## 4. 第四组：瘦身和工程卫生（里程碑 M3，可与前面并行）

### FX-18 归档不可达代码 ｜P2｜对应 S-1｜需要 OD-B 选 ①

**步骤**

1. 用 `evidence/audit_static.py` 在当时的 `main` 上重新生成可达与不可达清单（代码已经变了，
   不要直接用本交接包里的 `unreachable_modules.tsv`，它只是基线）。
2. 定保留名单，至少包括：
   - V1 真实运行链路的 11 个模块：`research_codex_exec`、`research_codex_process`、
     `research_codex_profile`、`research_process`、`research_process_windows`、
     `research_process_linux`、`research_claude_exec`、`research_claude_profile`、
     `research_claude_operator`、`research_linux_relay`、`team_research_glm`；
   - BTC 证据聚合与批量预测的 13 个模块：`team_evidence_aggregation` 及其
     `_attempt_psycopg`、`_attempt_store`、`_db_row`，`crypto_btc_evidence_catalog`、
     `_policy`、`_registry`、`_resolution`，`crypto_btc_forecast_service`，
     `supabase_team_evidence_aggregation_config`，`team_evaluation_attempt_latest_read`，
     `team_forecast_build_envelope`，`team_forecast_batch`；
   - 第 3 级设计可能用到的纸面经纪与订单生命周期模块；
   - 你点名要留的任何模块。
3. 打标签 `pre-prune-2026-11` 并推送。取回任何文件的命令写进计划记录：
   `git checkout pre-prune-2026-11 -- <路径>`。
4. 按家族分批，每批一个节点、一个独立复审。基线时各家族的不可达规模：

   | 模块名前缀 | 不可达模块数 | 不可达行数 |
   | --- | ---: | ---: |
   | `research_` | 1,124 | 1,278,558 |
   | `market_` | 399 | 402,380 |
   | `strategy_` | 332 | 257,173 |
   | `team_` | 127 | 112,363 |
   | `candidate_` | 65 | 63,194 |
   | `probability_` | 90 | 46,510 |
   | `paper_` | 102 | 38,699 |
   | 其余 | 199 | 116,421 |

   保留名单里的模块分布在 `research_`、`team_` 和"其余"几个家族里，分批时逐个剔除。
5. 每批删除：模块本身、只导入这些模块的测试、根包 `__init__.py` 里对应的导出。同步更新几份
   清单文档和钉住它们的测试：`docs/index/phase1-module-index.md`（对应
   `tests/test_phase1_docs_module_index_matches_files.py`）、
   `docs/testing/phase1-node-test-manifest.md`（对应 `tests/test_phase1_targeted_test_manifest.py`）、
   `docs/reports/phase1-report-registry.md`。
6. **不删**：任何迁移文件、迁移清单里的任何条目、数据库里的任何表。

**每批的门**：全量离线验证通过；删除前后的可达清单完全相同；`selfcheck` 10/10；剩余全部模块
编译通过。

**完成标志**：不可达模块数不超过保留名单；源码低于 25 万行。

### FX-20 根包改成按需导入 ｜P2｜对应 S-4

- `src/polymarket_alpha_lab/__init__.py`：把对 76 个模块的模块级导入换成一张"名字到模块"的表（现在是
  369 个名字，从现有导入语句机械生成），加模块级 `__getattr__` 在首次访问时导入并缓存，
  `__all__` 和 `__dir__` 保持原有名字集合。
- `from polymarket_alpha_lab import X` 的写法照常可用。

**验收**：`evidence/init_reach.py` 报告 `papersim.cli` 启动加载的模块不超过 20 个；
`python -X importtime -c "import polymarket_alpha_lab.papersim.gates"` 的输出里不出现第一代模块；
全量离线验证通过。

**注意**：先找出断言根包导出或导入副作用的测试再动手。

### FX-21 令牌的传递方式 ｜P3｜对应 E-1｜默认不做；要做需要你确认

**先知道两件事**

- 现在的做法是有意的：`cli.py:3089-3090` 注明令牌由调用方提供，代码不从环境变量或磁盘读取
  凭据。把它改成"读文件"会推翻这条边界。
- `tests/test_phase1_live_surface_guard.py` 限制 `cli.py` 里的标识符：凡是含 `apitoken`、
  `credential`、`auth` 等片段的名字都不允许，只放行 `api_token` 和 `llm_api_token` 两个。新增
  `llm_api_token_file` 这样的名字会直接让这个测试失败。

**什么时候才值得做**：核实项 V-5 表明第一代的 LLM 预测路径还在使用，并且 OD-B 没有把第一代
归档。否则不做。

**不动边界的做法**：沿用现有的 `--llm-api-token`，约定它的值为 `-` 时从标准输入读取一行。
不新增任何带令牌字样的标识符（读取用的辅助函数起一个不含上述片段的名字），不读环境变量，
不读磁盘，令牌也不再出现在进程列表里。原来直接传值的用法保持可用。

**验收**：守卫测试不改且通过；值为 `-` 时从标准输入取到令牌、不回显；直接传值的行为不变。

因为它碰的是凭据处理这一面，动手前需要你一句话确认。

### FX-22 最小工具链 ｜P3｜对应 S-5

- `pyproject.toml` 的 pytest 配置加 `filterwarnings = ["error::SyntaxWarning"]`。这一项提前到 M0
  的工程泳道做，但必须排在 FX-14 修好 `tests/test_papersim_gates.py:847` 之后合并。其余三项在 M3。
- 开发依赖加一个静态检查器，只对 `papersim/`、`tools/` 和新增代码启用最基本的规则（语法错误、
  未定义名字、无效转义）。不对第一代和 7 月模块开，噪音太大且它们即将归档。
- 对 `papersim/` 开覆盖率并设下限（建议 90%）。
- 新增依赖要更新 `uv.lock`，需要联网，在开发机上做。

### FX-23 正本仓库和分支清理 ｜P2｜对应 G-5、G-7｜需要 OD-C

- 按 OD-C 的结果更新 `docs/releases/linux-preview-release.md:24` 等处对两个仓库关系的描述
  （追加更正，不改写发布记录本身）。
- 每次推送后比较两边 `main` 的提交号，记进计划记录；不一致就停下来查原因。
- 核实 4 个未关闭 PR（#34、#35、#41、#67）是否已被取代，逐个留言说明后关闭。
- `handoff/`、`audit/`、`review/` 这几类分支是留存证据，不动；已合并超过 60 天的 `feature/`
  分支在核实已合并后可以删。

### FX-24 服务器地址 ｜P3｜对应 E-2

- 只改仍在使用的文件：`docs/development/linux-local-setup.md`、`league_strength.py` 的注释、
  三个测试文件里的注释，改用主机别名，真实地址放在各人自己的 SSH 配置里。
- 历史证据文档（发布记录、状态交接、评审存档）不改。
- `AGENTS.md` 里的那一处随 FX-25 一起处理。

### FX-25 整理 `AGENTS.md` ｜P2｜对应 G-8｜需要 OD-E，且成文后需要你过目

- 结构调整为：第一部分"现行规则"（一页，逐条现行、无历史措辞）；第二部分"铁律"（按现行含义
  重写措辞，例如铁律 1 直接写原生 PostgreSQL）；第三部分"历史"（被覆盖的旧段落原样移入）。
- 新增的内容就是 OD-E 的四处：把模拟盘主线正式写进规则，并记录你 11-01 把它纳入项目的授权
  原话；蓝图 8.2 的"做完的定义"；输入快照文件的地位；是否按线拆分记录。
- 3 个测试直接读取 `AGENTS.md`（见第 0 节第 3 条），其中
  `tests/test_codex_node_push_policy_rules.py` 按小节标题切分。要么保留这些标题，要么同一节点里
  更新测试。
- 这是你的规则文件：代理起草，你确认后才合并。

## 5. 第五组：验证期内的模型检查（里程碑 M4）

### FX-19 检查足球模型的联赛整体水平 ｜P2｜对应 P-10｜只读分析

1. 对每个联赛，用当前快照算本赛季和上赛季的"每队每场 xG 均值"之比 c；数据源混用的联赛按来源
   分开再算一次。
2. 用 WP-P4 走前回放的逐场结果，按轮次分组算"预测总进球减实际总进球"的均值，看它是否随赛季
   进度由负转正。
3. 判据：c 偏离 1 超过 3%，或第 2 步的偏差显著，就把"加入本赛季联赛整体水平项"作为一个影子
   变体做出来，走与 WP-P4 相同的验证门；在通过之前不改生产模型。两项都不成立就在计划记录里记
   "假设不成立"并关闭。

## 6. 明确不建议做的事

| 事项 | 为什么不做 |
| --- | --- |
| 重构或拆分 `cli.py` | 它属于第一代；在 OD-B 定下来之前重构等于给可能归档的代码投资 |
| 为了让某个队列或某个联赛过关而调整冻结阈值 | 11-07 评审的裁定仍然有效 |
| 把 7 月模块"接上入口"来降低不可达比例 | 没有数据源喂它们；接上只会把问题从"不可达"变成"可达但无用" |
| 现在给备份加密 | 已有文档警告且备份不进仓库；等有真实价值的数据再做 |
| 在本阶段写任何真实下单相关的代码 | 铁律 3 |
