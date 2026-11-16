# PR #34 内容级核对报告（FX-23 / V-8）

- 核对日期：2026-11-15。核对基线：本地 main = `4c8bec2fdce31fec3a8ec06a6ab93a25e4d7fc69`（fork `wmqfl861/polymarket-alpha-lab` 当前 main，与服务器 srv/main 一致）。
- 数据来源：`gh api repos/wmqfl861/polymarket-alpha-lab/pulls/34`（元数据、files、comments、reviews，实时只读）；PR base/head 完整对象均在本地仓库，diff 由本地 git 固定 SHA 计算，不使用 API 截断 patch。
- 本报告是 V-8 内容级核对：核对 PR 变更内容是否被完整保留或被明确退役；不是 FX-13（加密到期价 above/below、YES/NO 概率互补、对称报价边际镜像、触价锚点不变的业务方向语义）的验证。FX-13 已通过与本 PR 无关，也不能证明本 PR 已被取代。

## 1. PR 当前状态（实时 GitHub，2026-11-15）

| 项 | 值 |
|---|---|
| 标题 | WP-05: cost-aware paper scenarios joined to original strict research evaluation |
| 状态 | **open**（未合并、未关闭；无 merge commit） |
| base | `main` @ `4a6e787e1b0a6fb93c0d36455987c66f0b043e7c`（Merge PR #33） |
| head | `feature/wp05-research-paper-20260915` @ `ee0a3c07be2b2a3255dbb2c6365731145d218e16`（2 commits） |
| head 仓库 | wmqfl861/polymarket-alpha-lab（同仓库分支） |
| 规模 | 12 files，+1217/−5 |
| 祖先关系 | `ee0a3c07` **不是** main `4c8bec2f` 的祖先（`git merge-base --is-ancestor` 实测） |

PR 会话记录（issue comments 3 条 + reviews 2 条，均为 wmqfl861 自审性质）：
- 首头 `99d079bc` 全量离线门禁首轮 FAILED（1 failed/37597 passed）：新模式的全局异常处理破坏了旧契约 `tests/test_research_evaluation_cli.py::test_keyboard_interrupt_not_converted_to_a_database_failure`。
- 修正头 `ee0a3c07` 将 sanitized KeyboardInterrupt/SystemExit 处理限定在显式 paper 模式，非 paper 模式原样重抛原异常；离线/kit 门禁 PASS（37604 passed/36 skipped；96 passed），native 最终证据当时仍 pending。
- 结论当时明确：WP-05 PARTIAL、G5 open、native 未完成、未授权合并。PR 从未合并。

## 2. 合并文件列表与当前 main 的对应关系

| PR #34 文件（base→head 变更） | 当前 main 4c8bec2f 状态 | 说明 |
|---|---|---|
| `src/polymarket_alpha_lab/research_paper.py`（新增 362 行） | **存在但为重写版**（266 行，`710313dc` 引入） | 同名不同实现；符号面不同（见 §3） |
| `src/polymarket_alpha_lab/research_paper_input.py`（新增） | **不存在** | stdin 场景解码 `decode_paper_scenarios` 未进入 main |
| `src/polymarket_alpha_lab/research_paper_service.py`（新增） | **不存在** | 其职责并入 main 版 `research_paper.py` 的 `evaluate_research_paper_with_psycopg` |
| `src/polymarket_alpha_lab/research_evaluation_cli.py`（+36/−3） | **存在，已改**（当前无 `--paper-stdin`） | main 走 `--settled-paper` 演化路线（`2900b081`、`819e5bfa`） |
| `src/polymarket_alpha_lab/project_postgres/research.py`（+4） | **存在，已改** | PR 的 `evaluate_paper` 在 main 上为 `evaluate_paper_research`（research.py:142，懒加载 `research_paper.evaluate_research_paper_with_psycopg`） |
| `tests/test_research_paper.py`（新增 354 行） | **存在但为重写版**（`710313dc` 引入，215 行起，后演化） | 测试意图同族，用例不同 |
| `tests/test_research_paper_review.py`（新增 127 行） | **存在但为重写版** | main 版无 Fraction oracle（见 §4） |
| `tests/test_project_postgres_confirmation_native.py`（+32） | **存在，PR 追加内容未保留** | main 的纸面原生证明改由 `tests/test_project_postgres_paper_native.py` 承担 |
| `.github/workflows/native-distribution.yml`（+2） | 存在，独立演化 | PR 的行级改动不在 main |
| `.github/workflows/native-postgres.yml`（+3/−1） | 存在，独立演化 | 同上 |
| `DELIVERY_PLAN.md`（+33/−1，新增 §16） | 存在，main 走了另一条 §16（`710313dc` 链） | PR 的 §16 文本未进入 main |
| `docs/research-evaluation-console.md`（+194） | 存在，独立演化 | main 版文档描述 `--settled-paper`，不描述 `--paper-stdin` |

## 3. 验收声明 vs 当前实际状态（内容矩阵）

PR 原始要求 → 固定 base/head 上的实现 → 当前 main 对应实现（首次引入提交）→ 判定：

| # | PR #34 声明的核心内容 | main 上的对应 | 判定 |
|---|---|---|---|
| 1 | 严格完整历史复用、first-attempt 选择、incomplete 阻断、所有尝试/拒绝可见 | `710313dc` `research_paper.py` `_scenario` + `evaluate_research_paper_with_psycopg`；main 测试 `test_no_hiding_missing_inputs_failed_and_later_attempts`、`test_managed_assembly_reuses_complete_history_and_immutable_lookup`、`test_incomplete_history_block_is_not_bypassed` | 等价 |
| 2 | 精确原请求/记录/事件绑定、原合约与观察时刻门禁 | main `_scenario`：`original_terms_changed`、`paper_decision_time_invalid`、`market_time_invalid`、`assess_crypto_observation_time` 复用、crypto_btc/crypto_eth 白名单 | 等价 |
| 3 | 显式 Yes/No token 映射、两侧按对应 token 的 ask 深度模拟买入 | main `_scenario`：labels/tokens 校验 + `simulate_order_book_fill(PaperOrder(b.token_id,'buy',...))` 两册 | 等价 |
| 4 | 未舍入 walked notional、保守向上成本边界、不重复收价差/深度费用、费用显式提供 | main `fee_peak = min(price, max(f.best_ask, .5))`、ROUND_CEILING/ROUND_FLOOR 边界、`entry_notional_upper_bound` 等；review 测试 `test_cost_rounding_must_not_promote_a_subthreshold_edge`、`test_worst_price_fee_alone_is_not_a_fee_upper_bound` | 等价 |
| 5 | 六位有界 Decimal 输入、ambient decimal context 不改变结果 | main `research_paper_inputs.bounded_decimal`（六位）、测试 `test_ambient_decimal_context_cannot_change_result` | 等价 |
| 6 | 不自动缩量/重试/持久化/提供商调用；typed receipt | main：只提供全量或拒绝（`Offer only a complete-size alternative` 注释与 `test_depth_changes_execution_price_and_does_not_resize_partial`）；结果类型 `ResearchPaperEvaluation` | 等价（持久化路线 main 后续另有 capture/settlement，仍是 paper-only） |
| 7 | 非_paper 模式 KeyboardInterrupt/SystemExit 原样传播；仅显式 paper 模式加 sanitized 边界 | main CLI 无 paper-stdin 模式；原契约测试 `test_keyboard_interrupt_not_converted_to_a_database_failure` 仍在且未放宽。PR 关心的回归在 main 上不存在（因为该模式不存在） | 部分覆盖（PR 的 paper 模式中断语义随 stdin 模式一起未进入 main） |
| 8 | 托管会话入口 `evaluate_paper` | main `ProjectResearchSession.evaluate_paper_research`（research.py:142） | 等价（改名） |
| 9 | CLI `--paper-stdin` 有界 stdin 场景输入 + `research_paper_input.decode_paper_scenarios`/`MAX_INPUT_BYTES` | **未覆盖**：main 控制台无 stdin 场景模式；场景摄入走 `research_paper_operator.read_scenario`（带 record_id/input_sha256 绑定）+ capture 链 | **未覆盖**（被不同架构取代：内存 what-if → 同库留痕 capture/settlement） |
| 10 | 独立 Fraction 金额 oracle（240 组合） | main 测试用精确 Decimal 字符串断言（如 `average_price=='0.460'`），无独立 Fraction oracle | **部分覆盖**（精确断言存在；独立有理数对照法未保留） |
| 11 | 原生 PG 场景证明（未决/已结算成本、真实控制台、重启保全、真实 incomplete 拒绝） | main `tests/test_project_postgres_paper_native.py::test_paper_assembly_replays_reads_preserves_failures_and_blocks_incomplete` + `research-paper.yml`（windows-2025，18 个相关测试文件） | 等价（文件与用例名不同） |
| 12 | workflow 路由（native-distribution/native-postgres 微调） | main 的 `research-paper.yml` 独立工作流（`710313dc` 引入）承担；两旧 workflow 独立演化 | 部分覆盖 |

## 4. 替代实现 SHA

- **`710313dcd567e9eb06d4e0a1f55f56375d44c89c`**（2026-09-15 17:08 +0800，直接提交于 main，单亲 `4a6e787e`＝本 PR base，非本 PR 分支合并）：引入 main 版 `research_paper.py`、`research_paper_inputs.py`、`research-paper.yml`、`docs/research-paper.md`、`test_project_postgres_paper_native.py`、重写版两测试文件。
- 后续链：`6553a724`（capture 留痕）、`9349b5ac`（settlement 快照）、`5f232e5d`（任务 CLI 暴露 capture/inspect）、`2900b081`（`--settled-paper`）、`819e5bfa`（fail-closed）。以上均为 main 祖先。
- patch-id 实测：PR diff `e03cc85f…` ≠ `710313dc` diff `a69b0667…` → 是重写/替代实现，不是 cherry-pick。

## 5. 推荐动作与未解决项

- 内容判定：**核心场景组合语义＝等价保留（经替代实现）；stdin what-if CLI 模式与独立 Fraction oracle＝未覆盖/部分覆盖**。
- 未覆盖项是否仍在现行范围内：stdin 一次性 what-if 评估属于 2026-09 V1 第一代控制台形态；当前 V1 主线是 papersim（BTC/ETH 研究+纸面），且 `--settled-paper`/capture/settlement 链提供了带留痕的替代。stdin 模式是否还需要，属 owner/协调者决定，不在本核对中替答。
- 推荐：协调者在发布逐 PR 说明后关闭 #34，注明“被 710313dc 及其后续链取代；stdin 模式与 Fraction oracle 未保留，如需要应作为新工单”。关闭/留言由协调者执行（本节点不做远端写操作）。
- 未解决项：PR 会话中 native 最终门禁当时 pending——因 PR 未合并，该证据缺口随关闭归档，不影响 main 现状。
