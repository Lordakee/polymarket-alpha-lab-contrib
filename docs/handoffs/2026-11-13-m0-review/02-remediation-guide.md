# 02 整改指引（2026-11-13）

对应 [01-review-report.md](01-review-report.md) 的每一条发现，写明改哪里、怎么改、怎么验收、有什么坑。
行号对应被审核的提交 `b5ab6108d9e72ee37ce43f8247221f4f674d1224`；动手前先确认行号还对得上，对不上
以符号名为准。审计方没有运行过仓库代码，下面的改法是读代码得出的，以你在 Linux 上的实测为准；
实测与这里的判断不符时，按事实办并在交回的文档里单列。

## 0. 这一轮的规矩

1. **先修红灯。** 两条工作流（离线验证、真实数据库）都绿之前，除了本文列出的整改节点，不向 `main`
   推送任何新功能节点。M1 各条目的计划和计划复审是只读工作，可以并行做。
2. **一个节点一个聚焦提交，一次独立只读复审。** 复审的结论和发现摘要写进计划记录。没有"只改测试
   或文档可以不复审"的例外。
3. **每次推送后记下 CI。** 被触发的每条工作流都记运行编号和结论；失败就先分清是哪一类原因，再继续。
4. **不放宽测试。** 改测试时在节点计划里写两句话：它原来证明什么，改完之后证明什么。
5. **不改写历史，不强推。** 已经推上去的内容用后续提交更正。
6. **不要修改 `docs/handoffs/2026-11-12-audit/` 和 `docs/handoffs/2026-11-13-m0-review/` 下的文件。**
   它们有校验值清单。需要更正的地方写在计划记录里。
7. 冻结项、三个守卫测试、已有迁移照旧不动。线上账本数据库这一轮只读。
8. 连库时让客户端通过 `PAPERSIM_PG_PASSWORD_FILE` 读密码文件是既有机制，可以用；不打印、不复制、
   不提交。除此之外不读 `~/pal-artifacts` 下的其它文件；确有需要（例如 R-07 要看数据库日志），先在
   节点计划里写明并经复审。

## 1. 节点一览

| 节点 | 对应发现 | 改动的文件 | 泳道 |
| --- | --- | --- | --- |
| R-01 | P1-1 | `tests/test_papersim_intl_data.py` | 1 |
| R-02 | P1-3、P1-2 的 dispatch 部分 | `tests/test_project_postgres_uncapped_audit_native.py`、`…_confirmation_native.py`、`…_dispatch_cli_native.py`、`…_uncapped_native.py` | 2 |
| R-03 | P1-2 的 storage 部分 | `tests/test_project_postgres_native.py`、`…_backup_native.py`、`…_version_switch_native.py` | 3 |
| R-04 | P1-2 的纸面桥部分 | `tests/test_project_postgres_paper_native.py`、`…_paper_operator_native.py`、`…_paper_settlement_native.py` | 4 |
| R-05 | P2-1、P2-2、P2-4（文档部分）、P2-5、P2-6、P2-8、P2-9（登记）、P3-1、P3-2、P3-5 至 P3-8、P3-10 | `DELIVERY_PLAN.md`、`docs/handoffs/2026-11-12-m0-execution-review.md`、`docs/paper-sim/ledger-snapshots/2026-11-12/VIEW-DIFF.md`、`docs/paper-sim/server-mirror/MANIFEST.sha256`、`…/REDACTIONS.md` | 协调者 |
| R-06 | P2-4（代码注释部分）、P3-3、P3-4 | `src/polymarket_alpha_lab/papersim/ledger.py`、`fees.py`、`__init__.py`、`tests/test_papersim_fees.py`、`.gitattributes` | 5 |
| R-07 | P2-3 | 服务器只读调查，结果交给协调者落笔 | 服务器 |
| R-08 | P1-4、P2-7 | 不改文件：复审范围和提交方式 | 全部 |
| R-09 | M0 出口 | 手动触发真实数据库工作流；记录 | 协调者 |
| R-10 | 交回复审 | `docs/handoffs/2026-11-13-m0-remediation.md`（新） | 协调者 |

R-01 到 R-07 互不重叠，可以同时开。P3-9、P3-11 这一轮不改，登记进计划记录，分别并入 FX-09、FX-15。

## 2. 各节点

### R-01 修 `test_fetch_politeness_and_retry`（P1-1）

**现状**：`tests/test_papersim_intl_data.py:682-703`。测试把 `time.sleep` 换成"只记录不等待"，但
`time.monotonic` 还是真实时钟。第一次请求失败后退避 `sleep(5.0)`；第二次请求前，
`src/polymarket_alpha_lab/papersim/intl_data.py:270-278` 的 `_polite_pause` 算出"还差 2.0 减去真实
流逝的几十微秒"，于是记录到 1.99998。`:695` 断言每个记录值不小于 `SLEEP_S`，在时钟粒度细的 Linux 上
失败。

**改法**（只改测试，不改 `intl_data.py`）

1. 用可控时钟：做一个替身，带上 `intl_data` 用到的三个成员——`monotonic`、`sleep`、`time`（最后
   一个直接转给真实的 `time.time` 即可）。`sleep(x)` 把时钟往前拨 `x` 并记录 `x`。用
   `monkeypatch.setattr(intl_data, "time", 替身)` 只替换 `intl_data` 模块里引用的 `time`，不要改
   全局的 `time.monotonic`。在假的 `urlopen` 里记下每次请求时的时钟读数。
2. 重试场景的断言改成：两次请求之间的时钟间隔不小于 `SLEEP_S`（实际等于退避的 5.0），并且
   `sleeps == [5.0]`。
3. 新增一个不带重试的场景，直接证明礼貌间隔：`fetch_eloratings_current` 连发两个请求
   （`:663` 起已有它的用例），在可控时钟下两次请求的间隔应当恰好等于 `SLEEP_S`，
   `sleeps == [SLEEP_S]`。

**验收**：Linux 和 Windows 上都通过；推送后离线验证工作流为绿，记下运行编号。

**注意**：`_no_spacing`（`:619-621`）改的是全局 `time.sleep`，别的测试在用，不要动它。不要把阈值
改成"略小于 2.0 也算过"。

### R-02 恢复升级证明，补齐 dispatch 分区的字符串钉（P1-3、P1-2）

**改法**

1. `tests/test_project_postgres_uncapped_audit_native.py` 的第一个测试（`:56` 起）：
   - `:29` 的 `TAIL` 改回 `'20260919000000_research_uncapped_audit.sql'`。
   - `:69` 读出清单之后，照 `tests/test_project_postgres_paper_capture_native.py:53-57` 的写法：先删掉
     测试目录里第 68 条之后的迁移文件，把清单截到前 68 条，加一行注释说明这是保留历史上的 67→68
     证明；`:70` 的断言改回 `== 68`。
   - `:69` 的 `full` 后面在 `:88` 被原样写回清单文件，所以 `full` 也要换成截断后的 68 条清单的
     字节（`tests/test_project_postgres_backup_native.py:162-163` 是同样的处理）。否则补迁移那一步会
     应用 3 条而不是 1 条。
   - `:83`（67）、`:89`（1）、`:90`（0）、`:212`（`'68'`）不动。
2. 走全量清单的字符串钉改成 `'70'`：`tests/test_project_postgres_confirmation_native.py:179`、
   `tests/test_project_postgres_dispatch_cli_native.py:435`、
   `tests/test_project_postgres_uncapped_native.py:187`、
   `tests/test_project_postgres_uncapped_audit_native.py:688`、`:1778`。

**验收**：dispatch 分区在 Linux 上全部通过。复审报告里明确写一句：第一个测试升级的仍然是
`research_uncapped_audit` 这条迁移。

**注意**

- 逐个读测试的构造再改，不要按 grep 的结果整批替换。`evidence/pin_inventory.txt` 有全部计数字面量
  的清点和审计方的分类，可以当核对表；其中标 KEEP 的（`backup_native`、`budget_native`、
  `paper_capture_native` 里的 66、67）是历史证明，不要动。
- 修完第一处断言之后，同一个测试后面可能还有别的过期值，以 Linux 上跑到全绿为准。
- `:1778` 所在的测试需要显式开启容器化证明，CI 里跳过。能在服务器上跑就跑一次；跑不了就如实记
  "未运行"。

### R-03 storage 分区：端口占位、计数、版本切换（P1-2）

**改法**

1. 先在 Linux 上复现 `tests/test_project_postgres_native.py:188` 和
   `tests/test_project_postgres_backup_native.py:90` 的 `Address already in use`，确认原因（例如
   失败时看该端口上有没有 TIME_WAIT 连接）。
2. 确认是 TIME_WAIT 的话：两处占位 socket 在 `bind` 之前按产品代码同样的条件设置
   `SO_REUSEADDR`——仅在 `os.name == 'posix'` 时设，Windows 上不设。依据是
   `src/polymarket_alpha_lab/project_postgres/server.py:144-152` 的说明：Linux 上不设这个选项，残留的
   TIME_WAIT 会让绑定失败；设了之后，活着的监听者照样挡住别人。占位 socket 仍然 `listen()`，引擎
   仍然起不来，两处 `port_in_use` 的断言含义不变。
3. `tests/test_project_postgres_native.py:207` 的 `'68'` 改成 `'70'`。
4. `tests/test_project_postgres_version_switch_native.py`：它以运行时的 HEAD 为候选版本
   （`:755-759`），与目录规模有关的常量要整体跟上 70 条清单：
   - `:91` `CANDIDATE_CATALOG_ENTRIES` 改成 70；
   - `:93-97` `NEW_MIGRATIONS` 加上 `20261101000000_papersim_ledger.sql` 和
     `20261107000000_papersim_perf_view_fix.sql`；
   - `:1101`、`:1171` 的 `pending_migrations == 5` 和 `:1188` 的 `migrations_applied == 5` 改成 7；
   - `:1205` 的 `'68'` 改成 `'70'`；`:1211` 已经是 70；
   - `:777`、`:1177`、`:1181`、`:1191`、`:1219`、`:1228` 附近提示文字和文件名里的 68、five 一并
     改成一致的说法（不影响断言，但别留下互相矛盾的文字）；
   - `FEATURE_TABLES`（`:98`，在 `:663` 使用）检查的是"新迁移建的表在迁移前不存在、迁移后存在"。
     把两条模拟盘迁移建的表加进去是加强，不加也不算错；读完构造后决定，并在节点计划里写明。
   - OLD 一侧（固定提交 `2b20002c`、63 条）不动。

**验收**：storage 分区在 Linux 上全部通过，包括单独的"Prove native version switch"一步。

**注意**：如果复现后发现原因不是 TIME_WAIT，不要照第 2 步改；把现象写清楚，在节点计划里提出改法
并经复审。

### R-04 纸面桥三个测试的字符串钉（P1-2）

**改法**：`tests/test_project_postgres_paper_native.py:90`、
`tests/test_project_postgres_paper_operator_native.py:138`、
`tests/test_project_postgres_paper_settlement_native.py:196` 的 `'68'` 改成 `'70'`。

**验收**：这三个文件只由 `.github/workflows/research-paper.yml` 运行，那是只在 PR 时触发的 Windows
作业，直推模式下不会跑。在能跑原生 PostgreSQL 的环境里把它们各跑一次并记录结果；跑不了就如实记
"未运行"，不要写成通过。

**后续（不在这一轮做）**：纸面桥的原生测试现在没有任何会自动运行的 CI 通道，也没有 Linux 通道。
审计方的推荐是在 M3 给它补一个 Linux 作业和推送触发，做法与 FX-07 相同。登记进计划记录。

### R-05 记录和文档更正（协调者）

1. **交付书里的地址（P2-1）**：`docs/handoffs/2026-11-12-m0-execution-review.md:125` 把地址换成
   占位符或变量名，文末加一行带日期的更正说明。
2. **状态板重写（P2-5）**。至少包含：
   - 模拟盘主线：已结算 62 笔（另有 4 笔作废退款、5 笔未结算）；毛 +23.3%，净 +20.5%（入场加离场
     费，按 2026-11-12 费率表回推）；95% 区间约 −5% 到 +46%；最大市场占净盈亏约 38%；一句话结论
     "样本不足以宣称优势"。
   - 队列：跨联赛胜负盘写"已接线（代码路径证明）"，并列出两条保留意见和 OD-F 的两个附加条件；
     NBA、国际赛写影子。
   - V1：未激活（OD-A ①）；另起一格写 Linux 真实数据库 CI 的当前状态。
   - 仓库正本：`wmqfl861`（OD-C ①）。
   - CI：两条工作流各自最近一次运行的编号和结论。
   - 审计整改：M0 审核不通过（2026-11-13），整改中，待增量复审。
   - 八项决定及答复（照审核报告的表）。
   - 已登记的问题：结算标签（P2-9）、纸面桥没有 CI 通道（R-04）。
3. **§77 增补（P2-6）**：
   - 77.3 记 owner 2026-11-13 的两条原话和八项决定的表（原话见审核报告）。
   - 新增一小节记 M0 的完成情况：每条泳道的提交号、测试结果、复审结论；M0 批次复审的原文或摘要；
     全部 CI 运行编号，包括失败的（`evidence/ci_runs.txt` 可以直接引用）。
   - 偏差清单补全：交付书列的第 2 到 5 条；一个提交合并全部节点（P2-7）；在 Linux CI 为红时推送
     （P1-1）；三个提交没有复审（P1-4）；读了数据库日志（P3-7）。偏差 2 改成"不是偏差"（P3-6）。
   - 镜像没有加日期子目录（P3-8）：不要搬目录（清单和接线证明里的路径都要跟着改）；写明本次镜像
     日期是 2026-11-12，下次镜像放进带日期的子目录。
4. **V-6 的更正（P2-2）**：在 `DELIVERY_PLAN.md:3632` 下面追加更正，不改原文。要点：10-30 快照的
   盈亏合计是对的，本金少记了决策 #14 的 500 美元；截至快照时间已结算的是 41 笔，本金 11,454.36，
   毛盈亏 2,552.60，毛 +22.3%，净 +19.6%（入场费）或 +19.3%（入场加离场费）；+17.8% 和 +23.3% 都
   作废。
5. **V-2 的更正（P2-4）**：在 `DELIVERY_PLAN.md:3628` 下面追加：`forecast_calibration` 线上已是
   三个条件齐全的版本，依据 `forecast_calibration_viewdef.sql`。
6. **视图修改时间（P2-3）**：等 R-07 的结果，`DELIVERY_PLAN.md:3464` 和 `VIEW-DIFF.md:52-57` 两处
   统一；查不清就都写"未知，在 11-07 之后、11-12 之前"。
7. **净口径的口径（P2-8）**：状态板、§77 里引用净回报率的地方，统一用入场加离场费的数字，或者在
   数字后面写明口径。
8. **`VIEW-DIFF.md:78` 的校验值（P3-1）**：改成文件的实际值。`VIEW-DIFF.md` 自己的校验值登记在
   `docs/paper-sim/server-mirror/REDACTIONS.md` 里，改完要把那一行的现值一起更新。
9. **`MANIFEST.sha256`（P3-2）**：4 个脱敏文件的字节数改成现值；第 6 行改成"411 行与服务器逐字节
   一致，4 行已脱敏，见 REDACTIONS.md"。改完同样更新 `REDACTIONS.md` 里它自己那一行的现值。
10. **数字更正（P3-5）**：交付书 `:64` 的"11 处"追加更正为"15 行：14 个计数钉加 1 个 `TAIL` 常量"。
11. **V-8（P3-10）**：把四个未关闭 PR 的内容级核对做完并记录，或者写明并入 FX-23。
12. **登记（P2-9、P3-9、P3-11）**：结算标签的问题、`tools/` 里的数据库连接不在守卫范围、
    `intl_data.py:281-287` 的不限长度读取，各记一行，分别归入 FX-09、FX-09、FX-15。

**验收**：一个没读过项目的人只看状态板，能回答"几条线、各到哪、等谁、CI 是不是绿的"。在新提交上
重跑两个证据脚本（用法见各自开头）：`scan_mirror_tree.py` 的输出里 `size mismatch=0`，命中列表里
不再有交付书那一行；`address_occurrence_diff.py`（基线 `e8c8a95`，对新提交）里"新出现该地址的文件"
只剩镜像里那个第三方测试夹具。

### R-06 代码侧的三件小事

1. **过时的说明（P2-4）**：`supabase/migrations/20261101000000_papersim_ledger.sql:13-18` 和
   `src/polymarket_alpha_lab/papersim/ledger.py:643-648` 里"线上视图仍缺一个条件"这句已经过时，但
   这两处是迁移正文和它的逐字副本，**不能改**（`tests/test_papersim_ledger.py:39` 要求逐字节
   相同）。在 `ledger.py` 顶部的模块文档字符串里追加一条带日期的更正，写明：线上
   `forecast_calibration` 在 2026-11-12 的快照里已是三个条件齐全的版本；迁移正文里的那句话是
   2026-11-01 的历史陈述。`docs/paper-sim/usage.md` 里如果有同样的说法，一并追加更正。
2. **`.gitattributes`（P3-3）**：镜像目录那一行去掉 `-diff`，保留 `-text -whitespace`。
3. **`scan_fee_category`（P3-4）**：推荐改名为 `legacy_scan_fee_category`，并在文档字符串里写明
   "只用于回溯历史账本，不得用于新的入场决定"。涉及 `fees.py:27`、`:197`，`ledger.py:95`、`:527`、
   `:569`，`papersim/__init__.py:74`、`:326`，`tests/test_papersim_fees.py:186`、`:193`、`:195`。导出
   总数不变，selfcheck 的计数行不变。FX-08 的总入口必须显式传类别，这一条写进 FX-08 的验收。

**验收**：全量离线验证通过；selfcheck 10/10；`git diff` 能正常显示镜像目录里文件的改动。

### R-07 查清视图是什么时候改的（P2-3，服务器只读）

成功的 DDL 没有日志，可以用系统目录里的事务号把时间夹出来，全部是只读查询：

1. 读两个视图在 `pg_class` 和 `pg_rewrite` 里那几行的 `xmin`。`CREATE OR REPLACE VIEW` 会重写
   `pg_rewrite` 里的规则行，它的 `xmin` 就是最后一次改视图的事务号。
2. 读 `decisions`、`resolutions`、`bankroll` 各行的 `xmin` 和它们自带的时间戳。没被更新过的行，
   `xmin` 就是插入它的事务号。
3. 找出事务号刚好小于和刚好大于视图那个事务号的两行，它们的时间戳就是改视图时间的下界和上界。
4. 再对照同一时间段的操作记录（轮次目录里的日志、`review/FIXES.md`）。

把结论、用到的查询和两条夹住它的记录交给协调者落笔。夹不出来就如实写"未知，在 11-07 之后、
11-12 之前"。同时在计划记录里立一条规矩：在账本 v2 的受管流程落地之前，线上库的任何 DDL 都要在
执行当时记一行（时间、语句文件的校验值、执行人）。

### R-08 复审范围和提交方式（P1-4、P2-7）

- R-02、R-03、R-04 的复审范围明确包括 `a93f5fab` 和 `15c35a62` 的全部改动，逐行确认每个被改的值
  是"全量清单的计数"还是"历史证明里的常量"。
- R-05 的复审范围包括 `b5ab6108`。
- 从这一轮起一个节点一个提交。`e45c3142` 不拆、不改历史，记为偏差。

### R-09 M0 出口

1. R-01 到 R-06 都合并之后，在同一个提交上：离线验证为绿；手动触发真实数据库工作流为绿（四个
   Linux 分区加版本切换一步）。两个运行编号记进 §77。
2. 逐条重核开发计划 4.4 的九个勾选项。第 5 项（最近一次扫描记录了代码提交号）以 11/14-17 那一轮
   扫描的输出为准，届时补记；交回复审时如果那一轮还没跑，写"待下一轮扫描"。

### R-10 交回复审

写 `docs/handoffs/2026-11-13-m0-remediation.md` 并推送到 `main`，内容：

1. 固定版本：本轮起点（合并本交接包之后的提交）、每个整改节点的提交号、终点提交号。
2. 逐条处置表：发现编号 → 做了什么 → 提交号 → 证据（文件和行号、运行编号）。没做的写原因。
3. CI：两条工作流在终点提交上的运行编号和结论；过程中失败过的也列出。
4. 每个节点复审的结论和发现摘要。
5. "需本地 agent 复核"七项各自的结果（见审核报告）。
6. 偏差和未完成事项。

然后把终点提交号和这个文件的路径告诉 owner。审计方会做增量复审，把复审文档发布到仓库的保留分支，
并通过 owner 给出下一份提示词；交付书里不需要规定审计方的输出形式。

## 3. 八项决定的落地

| 项 | 现在要做的 | 解锁了什么 |
| --- | --- | --- |
| OD-A ① | 状态板写"V1：未激活"；不改 V1 源码 | 无。V1 的原生测试为了让 Linux CI 跑通可以修（R-02 到 R-04） |
| OD-B ① | 登记 | FX-18 可以做，但要等两条 CI 都绿、增量复审通过；先打标签 `pre-prune-2026-11`，按家族分批，每批一个节点 |
| OD-C ① | 登记；状态板写正本 | FX-23：更正两个仓库关系的描述（追加更正），每次推送后比较两边 `main`，四个 PR 逐个处理 |
| OD-D ① | 登记 | FX-09 进入 M1。第一步是给 `paper_sim` 集群设计受管的变更流程（它没有迁移台账），设计先过复审 |
| OD-E ① | 登记 | FX-25：起草 `AGENTS.md` 的整理稿，把平台约定（可在 Windows 上开发，以 Linux CI 为准）写进去；**owner 确认成稿之后才合并**。合并之前记录照旧写在 `DELIVERY_PLAN.md`，不新建分线记录文件 |
| OD-F ① | 状态板写"已接线"和两条保留意见 | 11-24 起可按 §75 的条件恢复。首笔跨联赛候选入场之前，扫描输出里要有 `cross_league_mw_check` 行并留证；该轮扫描记下代码提交号 |
| OD-G ① | 把蓝图 5.3 的六条晋级标准和 FX-17 的暂停规则原文抄进计划记录，注明登记日 2026-11-13 | FX-11 的晋级判定、FX-17 的暂停规则可以按原数字实现 |
| OD-H 不执行 | 记录现状（R-05、R-07） | 无。线上两个视图不动；它们的定义等 FX-09 的受管流程重新登记 |

## 4. 这一轮不要做的事

- 不要为了让 CI 变绿而跳过、删除或放宽任何测试，也不要把失败的测试挪出矩阵。
- 不要对线上账本数据库执行任何写操作，包括重跑视图迁移。
- 不要在两条 CI 变绿之前推送 M1 的实现；不要在增量复审通过之前开始归档（FX-18）。
- 不要改动 `AGENTS.md`；FX-25 的成稿要先给 owner 看。
- 不要修改两个交接包目录下的文件。
- 不要把服务器的公网地址写进任何新文件，包括写成正则、拆开写或者写进命令示例。
