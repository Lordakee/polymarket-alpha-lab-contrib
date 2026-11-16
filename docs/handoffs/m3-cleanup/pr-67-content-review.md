# PR #67 内容级核对报告（FX-23 / V-8）

- 核对日期：2026-11-15。核对基线：本地 main = `4c8bec2fdce31fec3a8ec06a6ab93a25e4d7fc69`。
- 数据来源：`gh api repos/wmqfl861/polymarket-alpha-lab/pulls/67`（实时只读，含 9 条会话评论全量）；base/head 对象在本地，diff 由本地 git 固定 SHA 计算。
- 本报告是 V-8 内容级核对，不是 FX-13 业务方向验证。**FX-13（加密到期价方向语义）已通过不能证明本 PR 已被取代；本 PR head 非 main 祖先也不能证明其行为未被重写合入——本报告逐文件核实了这两种可能。**

## 1. PR 当前状态（实时 GitHub，2026-11-15）

| 项 | 值 |
|---|---|
| 标题 | PAL 20260920 longtask: soak driver, property and oracle tests (ORIGINAL_CANDIDATE d929cc35, soak IN_PROGRESS; SIDECAR_CANDIDATE f2aff305) |
| 状态 | **open + draft**（未合并、未关闭；协调者评论多次明确 “Keep PR67 draft”） |
| base | `main` @ `199f5a4f629466467f638d7f4a383e4bead19120`（Merge PR #66） |
| head | `work/pal-parallel-20260921-ad7a9c77be5a497ab908bb33b031a182` @ `af8ee27438eba9c022bdb2d61c62c37b9b7fe8e0`（67 commits，2026-09-21～09-22） |
| 规模 | 46 files，+26148/−4 |
| 祖先关系 | `af8ee274` **不是** main `4c8bec2f` 的祖先（实测）；API `merge_commit_sha` `bf8c333a` 为 GitHub 预备合并位，本地无对象、从未物化（merged_at=null） |
| 内部候选 | `d929cc35`（ORIGINAL_CANDIDATE，2026-09-21）与 `f2aff305`（SIDECAR_CANDIDATE）均为本 PR 67 个提交中的中间提交，均在本地对象库 |

会话要点（9 条评论，2026-09-21～09-22，wmqfl861 协调者）：协调者对 pinned 源跑有限 stdlib 探针，先复现 7 个、后 9 个具体函数级反例（gate 误判 PASS、合格轮计数混同、72h 容差吞掉观察下限、跨 segment 收据借用、wait_loop 写检查点违反只读范围、锁文件先读后截、恢复 unknown 丢失、linker 取消覆盖/-heal、64KiB JSON 前缀截断接受、Win32 错误映射）；批准最小 producer/receipt/auditor 改动与 11 场景+2 故障契约方案；授权且仅执行一次 kit 诊断重跑（attempt2 全绿，attempt1 1 失败保留）；多轮 handoff 分支发布（handoff/wp02-corrective-longtask-20260921、handoff/wp02-rv05-capacity-20260921、handoff/rv05-closure-20260922、handoff/rv05-linker-safety-20260922）；自动 launch 权限 HOLD；绝对战役截止 2026-09-28T00:36:41Z；全程 “Keep PR67 draft”、无 main 合并授权。

## 2. 合并文件列表与当前 main 的对应关系（46 文件全查）

**全部 42 个新增文件在 main 4c8bec2f 上不存在**（逐路径 `git cat-file -e` 实测）：

- 工作流：`.github/workflows/windows-soak-contract.yml`
- 契约/文档：`docs/contracts/ERRATA-001.md`、`docs/contracts/soak-subinput-receipt-v1.md`、`docs/contracts/soak-subinput-wiring-v1.md`、`docs/handoffs/rv05-control-safety/N3-INTEGRATION.md`、`docs/handoffs/rv05-control-safety/linker-subpatch-L7-L9.patch`、`docs/operations/soak-operations.md`、`docs/scenario-map-13-11-2.md`
- 启动资产：`launch/config-rv05-final-template.json`、`launch/manifest-rv05-final.json`
- 支撑库：`tests/support/__init__.py`、`tests/support/soak_audit.py`(1183)、`soak_audit_subinputs.py`(385)、`soak_closeout.py`(848)、`soak_driver.py`(1510)、`soak_linker.py`(2613)、`soak_okcompute.py`(1054)
- 测试：`test_packaged_session_drain_failure_witness.py`、`test_px02_gap_regressions.py`、`test_research_cross_module_composition.py`、`test_research_exec_boundaries.py`、`test_research_paper_settlement_decimal_oracle.py`(738，LT-03 独立 Decimal oracle)、`test_research_transport_stop_order.py`、`test_rv05_n2_launch_safety.py`、`test_rv05_n5_launch_review_rejection.py`(1075)、`test_soak_audit.py`、`test_soak_audit_subinputs.py`、`test_soak_closeout.py`、`test_soak_driver.py`、`test_soak_driver_recovery.py`、`test_soak_driver_subinput.py`、`test_soak_fault_contracts.py`、`test_soak_linker.py`、`test_soak_linker_l7_l9.py`、`test_soak_linker_review.py`、`test_soak_okcompute.py`（空占位）
- 工具：`tools/soakctl/` 全部 7 个文件（README、identity-template、launch-rv05.ps1、launch-spec-template、make_synthetic_terminal.py、preflight-rv05.py、run_final_review.py）

**4 个修改文件的 PR 改动均不在 main**：

| 文件 | main 现状 vs PR base 199f5a4f | PR 改动的命运 |
|---|---|---|
| `tests/test_research_capture_codec.py`（+7） | main 与 PR base **逐字节相同**（diff 为空） | PR 的 endDate UTC/DST 规范化（测试夹具修复，注释引用 round-182/625 producer-oracle 回归）**未进入 main** |
| `tests/packaged_session_drain.py`（+84/−3） | main 相对 base 独立 +18/−1（未含 witness） | PR 的 N4 drain 失败证人（DRAIN_WITNESS_* 封闭词汇、32 位十六进制退出码、异常标签）**未进入 main**（diff 实测：PR head 有、main 无） |
| `.github/workflows/native-postgres.yml`（+84/−3） | main 相对 base 独立 +315/−1 | PR 的行级改动不在 main |
| `DELIVERY_PLAN.md`（+189） | main 的 §46/§47 是不同内容（WP-06 证据保全 / WP-03 并发中断轮）；PR 的 §46/§47 为 RV05 收口/控制安全轮文本 | PR 章节从未进入 main |

**main 上不存在任何 soak/rv05/soakctl 替代实现**：`git grep -i soak` 全树仅命中 `docs/handoffs/2026-11-12-audit/evidence/github_api_facts.txt`（对 PR #67 元数据的审计摘录）；`rv05` 零命中；oracle 命中均为不相关的 candidate_*/market_* 评分模块。papersim（M0/M1 现行主线）自带自己的费用/评估测试矩阵（`tests/test_papersim_*`），与 PR #67 的 soak/oracle 体系无实现重叠。

## 3. 验收声明 vs 当前实际状态（内容矩阵）

| # | PR #67 内容块 | main 对应 | 判定 |
|---|---|---|---|
| 1 | 有界 soak driver（LT-01：STOP 竞态修复 `d929cc35`、恢复、子输入、故障契约） | 无 | **未覆盖** |
| 2 | 协议边界与停止顺序反例（LT-02：`test_research_transport_stop_order.py`） | 无 | **未覆盖** |
| 3 | 独立 Decimal oracle：合成 BTC/ETH 纸面与结算数学（LT-03：`test_research_paper_settlement_decimal_oracle.py`，738 行） | 无（main 的 WP-05 测试用精确 Decimal 字符串断言，非独立 oracle；见 pr-34/pr-35 报告） | **未覆盖** |
| 4 | PX-02 mutation-gap 回归（收据绑定、墙钟完成、缓存记账、none-as-zero 费用、费用舍入） | 无 | **未覆盖** |
| 5 | PX-03 失败/恢复确定性实验；PX-04 跨模块组合（claim/audit/paper/settlement 两协议客户端） | 无 | **未覆盖** |
| 6 | PX-05a 独立 bypass 终端 closeout 程序；soak audit/closeout/审计子输入 | 无 | **未覆盖** |
| 7 | N4 drain 失败证人（packaged_session_drain witness） | 无（diff 实证） | **未覆盖** |
| 8 | windows-soak-contract 工作流 + ERRATA-001 + 三份 soak 契约文档 + soak-operations + scenario-map | 无 | **未覆盖** |
| 9 | linker/launcher 安全（N2/N3：argv 白名单、RemoteSigned 合规、SUT/控制身份分离、L7-L9 子补丁） | 无；且 Windows 启动器属已退役的 Windows-only 范围（2026-09-27 owner 决定） | **未覆盖**（范围背景变化） |
| 10 | capture-codec 测试夹具 DST 规范化修复 | 无（main 夹具与 PR base 相同；main CI 当前绿，未观察到该潜在时区问题在现行矩阵中暴露） | **未覆盖**（未证实为现行必需） |
| 11 | 72h/864 有效轮/100k 合格输入的 soak 战役（ORIGINAL d929cc35 + SIDECAR f2aff305 + 各 handoff 分支证据） | 战役窗口绝对截止 2026-09-28T00:36:41Z 已过期；main 无任何对应记录 | **未覆盖**（战役已过期） |

## 4. 替代实现 SHA

**无。** 未发现任何把本 PR 内容（或其行为等价重写）合入 main 的提交：46 个文件路径在 main 全部缺席、4 个共享文件的 PR 行级改动全部缺席、关键词（soak/rv05/soakctl/ERRATA/witness）在 main 零实现命中。PR #67 的全部内容只存在于该 open draft 分支及其内部中间候选（d929cc35/f2aff305）和四个 handoff 证据分支。

## 5. 与 V-8 / FX-13 的区分（本 PR 专用说明）

- FX-13 验证的是加密到期价**业务方向语义**（above/below、YES/NO 互补、边际镜像、锚点不变），其通过与本 PR 的 soak/oracle 体系无内容重叠——FX-13 不能销项本 PR 的任何未覆盖项。
- 本报告（V-8）核实的是“内容是否完整保留或明确退役”：结论是**既未保留、也未经过任何明确退役决定**——它是一个被协调者多次审查、要求保持 draft、随后随 Linux-only 转向和 M0/M1 papersim 重心转移而自然搁置的 open draft。

## 6. 推荐动作与未解决项

- 内容判定：**未覆盖（46/46 文件 + 4/4 共享文件改动均不在 main，无替代实现）**。
- 退役/保留是 owner 决定，本核对给出事实依据：
  1. 战役窗口（绝对截止 2026-09-28）已过期近两个月，72h soak 无法按原条件补做；协调者评论中的 7+9 个函数级反例未在本 draft 上修复收口。
  2. 其 Windows 启动器/linker/soakctl 部分属已退役的 Windows-only 范围。
  3. 约 2.6 万行测试支撑库与 M3 FX-18 的 `<250,000` 行源码目标方向相反；papersim 主线已有自己的测试矩阵。
  4. 若有个别仍通用的小件（如 capture-codec 夹具 DST 规范化、独立 Decimal oracle 思路），应作为新工单按现行写域提取，而非整体合并。
- 推荐（供协调者/owner 决定后执行）：明确退役并关闭 #67（draft 状态 + 未修复反例 + 过期窗口 + 范围退役为依据），或在 owner 明确需要 soak 体系时按 Linux-only 新建工单重做。关闭/留言/分支处置由协调者执行；本节点不做远端写操作。
- 未解决项：PR 内 67 提交与四个 handoff 证据分支（handoff/wp02-corrective-longtask-20260921 等）在 fork 上仍保留；若最终退役，其证据保留要求与 §6.4 分支规则一致（handoff/ 类保留）。
