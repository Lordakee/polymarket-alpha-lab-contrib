# PR #35 内容级核对报告（FX-23 / V-8）

- 核对日期：2026-11-15。核对基线：本地 main = `4c8bec2fdce31fec3a8ec06a6ab93a25e4d7fc69`。
- 数据来源：`gh api repos/wmqfl861/polymarket-alpha-lab/pulls/35`（实时只读）；base/head 对象在本地，diff 由本地 git 固定 SHA 计算。
- 本报告是 V-8 内容级核对，不是 FX-13 业务方向验证；FX-13 通过与本 PR 无关。#35 与 #34 标题近似但为不同变更（不同 head、不同文件集、不同 CLI 标志），本报告独立结论，不与 #34 合并判断。

## 1. PR 当前状态（实时 GitHub，2026-11-15）

| 项 | 值 |
|---|---|
| 标题 | WP-05: original research to explicit-cost hypothetical paper replay |
| 状态 | **open**（未合并、未关闭；0 条评论、0 条 review——从未进入门禁流程） |
| base | `main` @ `4a6e787e1b0a6fb93c0d36455987c66f0b043e7c`（与 #34 同 base） |
| head | `feature/wp05-paper-replay-20260915` @ `103e6763112fdc065c56a17682ec0288eaa37499`（1 commit） |
| 规模 | 11 files，+1336/−3 |
| 祖先关系 | `103e6763` **不是** main `4c8bec2f` 的祖先（实测） |

## 2. 合并文件列表与当前 main 的对应关系

| PR #35 文件 | 当前 main 4c8bec2f 状态 | 说明 |
|---|---|---|
| `src/polymarket_alpha_lab/research_paper_inputs.py`（新增 213 行） | **存在但为重写版**（136 行，`710313dc` 引入） | 同名不同实现：PR 版含 `decode_scenarios`（stdin 解码）与 `MAX_INPUT_BYTES`；main 版为 `bounded_decimal`/`ResearchPaperBook`/`ResearchPaperScenario`/`content_hash`/`copy_scenarios`，无 stdin 解码 |
| `src/polymarket_alpha_lab/research_paper_evaluation.py`（新增 261 行） | **不存在** | 组合器 `compose_research_paper_evaluation`、`ResearchPaperReplay`、`evaluate_research_paper_with_psycopg` 未按此文件进入 main；等价函数并入 main 版 `research_paper.py`（`710313dc`） |
| `src/polymarket_alpha_lab/research_evaluation_cli.py`（+46/−2） | **存在，已改**（当前无 `--paper-scenarios`） | main 走 `--settled-paper` 路线 |
| `src/polymarket_alpha_lab/project_postgres/research.py`（+4） | **存在，已改** | main 为 `evaluate_paper_research`（等价改名） |
| `tests/test_research_paper_evaluation.py`（新增 319 行） | **不存在** | 其意图由 main `tests/test_research_paper.py`（重写版）承担 |
| `tests/test_research_paper_review.py`（新增 95 行） | **存在但为重写版** | PR 版含“控制台不信任任意返回字典（raw-leak/wrong-scenario）”反例；main 版反例集不同（见 §3 行 5） |
| `tests/test_project_postgres_paper_native.py`（新增 147 行） | **存在但为重写版**（`710313dc` 引入 94 行起，后演化） | main 版为 `test_paper_assembly_replays_reads_preserves_failures_and_blocks_incomplete` |
| `.github/workflows/research-paper.yml`（新增 57 行） | **存在但为重写演化版**（`710313dc` 引入 46 行，现跑 18 个测试文件） | 同名不同内容；PR 版跑 3 个测试文件的 replay 证明 |
| `.github/workflows/native-distribution.yml`（+2） | 存在，独立演化 | PR 行级改动不在 main |
| `DELIVERY_PLAN.md`（+29/−1，自拟 §16） | 存在，main 另有 §16 | PR 文本未进入 main |
| `docs/research-evaluation-console.md`（+163） | 存在，独立演化 | main 版描述 `--settled-paper` |

## 3. 验收声明 vs 当前实际状态（内容矩阵）

PR #35 声明（其自拟 §16）→ main 对应 → 判定：

| # | PR #35 声明 | main 上的对应 | 判定 |
|---|---|---|---|
| 1 | 显式有界输入绑定原请求/记录哈希、市场规则、Yes/No token、原始盘口、采集/模拟时刻、实验份数、全部成本参数 | `710313dc` `research_paper_inputs`（`ResearchPaperScenario` 绑定 record/market/books/decision_at/costs/gates）+ `_scenario` 全量校验 | 等价 |
| 2 | 原输入仅内存使用；完整研究分母与 incomplete 阻断不变 | main 原生测试断言 replay 幂等、 mutated `record_sha256` 拒绝、incomplete 阻断；`paper_trades_created=0` | 等价 |
| 3 | 失败/后续重复研究、未给盘口、时刻无效、深度不足、风险拒绝、结算未决分别可见 | main `research_paper.py` reason_code 族 + `test_no_hiding_missing_inputs_failed_and_later_attempts` | 等价 |
| 4 | 逐档精确金额、不用显示均价反推、不重复收深度滑点、费用显式提供（六位小数曲线） | main 复用 `simulate_order_book_fill` walked 金额；fee_peak 边界；`test_cost_rounding_must_not_promote_a_subthreshold_edge`、`test_worst_price_fee_alone_is_not_a_fee_upper_bound` | 等价 |
| 5 | 控制台只接受重新校验的类型化回执（不信任任意返回字典；已关闭市场必须拒绝） | main：typed `ResearchPaperEvaluation` + `_require(...'market_not_executable')`（active/closed/acceptingOrders/enableOrderBook）；review 反例为变异场景/市场形状/费率非零等（`test_mutated_nested_scenario_is_revalidated`、`test_market_shape_and_order_constraints_reject_without_fallback`）。PR 的 monkeypatch 假会话“raw-leak”反例本身未保留，但对应守卫在 main 以真实类型检查存在 | 等价（反例形式不同） |
| 6 | 结算前后选择不变、人工确认后原评估衔接 | main 原生测试覆盖 settlement 前后同结果（同场景重跑结果一致、确认后 replay 不变） | 等价 |
| 7 | CLI `--paper-scenarios` stdin 有界输入（`decode_scenarios`/`MAX_INPUT_BYTES`、paper 模式中断语义） | **未覆盖**（同 #34 行 9：main 无 stdin 场景模式） | **未覆盖** |
| 8 | `ResearchPaperReplay` 结果类型（history+scenarios+attempts 整体回执） | main `ResearchPaperEvaluation`（history 快照 + paper_attempts + 保守合计） | 等价（结构改名重组） |
| 9 | 独立 Fraction oracle 金额对照 | main 用精确 Decimal 字符串断言，无 Fraction oracle | 部分覆盖（同 #34） |
| 10 | 独立原生工作流不延长既有超时 | main `research-paper.yml`（windows-2025, 10min）独立运行 | 等价 |

## 4. 与 #34 的关系及替代实现 SHA

- #34 与 #35 同 base、并行开题、互不包含：#34 head `ee0a3c07`（12 文件）与 #35 head `103e6763`（11 文件）是两套独立实现；#35 无任何评论/review，从未走到门禁。
- 替代实现：与 #34 相同的 main 链——**`710313dc`**（2026-09-15 直接提交，非两 PR 分支合并）及其后续 `6553a724`/`9349b5ac`/`5f232e5d`/`2900b081`/`819e5bfa`。
- patch-id 实测：#35 diff `30adab42…` ≠ `710313dc` `a69b0667…`，也 ≠ #34 `e03cc85f…` → 三者互为独立实现。
- main 版吸收了两 PR 的共同语义（原研究绑定+逐档成本重放），但文件布局（inputs+单文件组合器）与入口（无 stdin 模式）是第三种设计。

## 5. 推荐动作与未解决项

- 内容判定：**重放组合语义＝等价保留（经替代实现 `710313dc` 链）；stdin replay CLI 模式与 Fraction oracle＝未覆盖/部分覆盖**（与 #34 的缺口同源，可一并处置）。
- 推荐：协调者关闭 #35，注明“与 #34 同被 `710313dc` 链取代；PR 从未进入评审/门禁，无已发布证据需要迁移”。关闭/留言由协调者执行。
- 未解决项：无 PR 侧待迁移证据；stdin 模式需求归属同 #34 §5。
