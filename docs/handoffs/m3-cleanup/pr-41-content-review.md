# PR #41 内容级核对报告（FX-23 / V-8）

- 核对日期：2026-11-15。核对基线：本地 main = `4c8bec2fdce31fec3a8ec06a6ab93a25e4d7fc69`。
- 数据来源：`gh api repos/wmqfl861/polymarket-alpha-lab/pulls/41`（实时只读）；base/head 对象在本地，diff 由本地 git 固定 SHA 计算。
- 本报告是 V-8 内容级核对，不是 FX-13 业务方向验证。

## 1. PR 当前状态（实时 GitHub，2026-11-15）

| 项 | 值 |
|---|---|
| 标题 | WP-06: first-invocation PowerShell handoff evidence without weakening gates |
| 状态 | **open**（未合并、未关闭） |
| base | `main` @ `f331d71d76d116aabee3661e73a9621d52e3a1d6`（Merge PR #40） |
| head | `feature/wp06-handoff-cold-evidence-20260915` @ `3056c1526d85e7f9a9fc3e53f6c6c964cb234010`（1 commit） |
| 规模 | 8 files，+600/−9 |
| 祖先关系 | `3056c152` **不是** main `4c8bec2f` 的祖先（实测） |

PR 会话记录（2 条评论 + 1 条 review，均为 wmqfl861 自审）：
- 冷启动 run34990955584 cmd/pwsh 两 job 均 SUCCESS（各 51 passed，18 条完整 stage 记录，首显式目标调用即原 success-powershell.exe 用例）；均未复现历史 30s 超时，PR #30 根因保持 OPEN。
- 全量离线 37837 passed/40 skipped、paper 回归 339 passed 均完成；native34990955317 当时仍 pending——未合并。
- 自审真实首败：诊断输出 BrokenPipeError 遮蔽 TimeoutExpired 并跳过 kill——修复为 protected diagnosis/finally cleanup，原失败断言保留。

## 2. 合并文件列表与当前 main 的对应关系

| PR #41 文件 | 当前 main 4c8bec2f 状态 | 对应替代 |
|---|---|---|
| `tests/handoff_probe.py`（新增 135 行：`trace_prelude`/`read_trace`/`run_traced`，30s 通信契约、8192B/64 条轨迹上界） | **不存在** | `f3537b27` 的 `tests/handoff_process_probe.py`（93 行：`summarize`/`run_fixture`，TIMEOUT_SECONDS=30，固定 STAGES 集，.NET 计时，POWERSHELL_PROBE） |
| `tests/test_handoff_probe.py`（新增 139 行） | **不存在** | `tests/test_handoff_process_probe.py`（`f3537b27`） |
| `tests/test_handoff_probe_review.py`（新增 71 行） | **不存在** | `tests/test_handoff_process_probe_review.py`（`f3537b27`） |
| `tests/test_handoff_download.py`（+43/−7） | **存在，已改** | `f3537b27` 同样改此文件（+48 行级不同但意图相同：stage 序列断言） |
| `.github/workflows/handoff-cold-start.yml`（新增 75 行，cmd/pwsh 矩阵首调用证据） | **不存在** | `.github/workflows/handoff-first-run.yml`（`f3537b27`，3 试次矩阵）+ `handoff-first-run-campaign.yml`（`b7f7d226` 预声明捕获战役） |
| `docs/development/windows-handoff-cold-start.md`（新增 113 行） | **不存在** | `docs/handoff-first-run.md`（`f3537b27`，98 行） |
| `.github/workflows/native-postgres.yml`（+3/−1） | 存在，独立演化 | PR 行级改动不在 main |
| `DELIVERY_PLAN.md`（+21/−1，自拟 §21） | 存在，main 另有对应章节 | main §46（2026-09-20/24 演化）记录同类推进 |

## 3. 验收声明 vs 当前实际状态（内容矩阵）

| # | PR #41 声明 | main 上的对应（首次引入提交） | 判定 |
|---|---|---|---|
| 1 | 原 18 个 shell 场景、顺序、30 秒通信门槛、原断言全部保留；生产下载脚本与运行代码不改 | `f3537b27` 提交文明确认“preserving all original assertions, production helper bytes and the 30-second process contract”；`docs/handoff-first-run.md`：“The production scripts/download_handoff.ps1 is byte-identical” | 等价 |
| 2 | 超时后采样进程状态、清理前输出受限摘要、传播原超时；缺失/坏轨迹不虚构阶段；不记录路径/环境/原始输出 | `handoff_process_probe.summarize`：固定 stage 名+时长、无路径/环境；`f3537b27` 文明示“Preserve primary errors if diagnostic sinks fail”（即 PR 自审发现的 BrokenPipe 遮蔽问题的同类防线） | 等价 |
| 3 | 独立 cmd/pwsh 父环境各执行原首个 PS5.1 成功场景；不预热、不改模块路径、不扩超时、不自动重试 | `handoff-first-run.yml`：windows-2025 矩阵 3 试次，首测试控制的 PS5 调用 + probe 契约；`b7f7d226` campaign 预声明捕获 | 等价（试次数与组织不同） |
| 4 | 阶段证据为工程诊断，不宣称修复 PR #30 根因、不关闭 G6 | `docs/handoff-first-run.md` §“The defect is still open”原文保留 | 等价 |
| 5 | Windows 下载验收冷启动证据（Windows-only 工程子任务） | 已交付于 main；其后 owner 2026-09-27 Linux-only 决定将 Windows 验收义务冻结为历史证据（AGENTS.md 现行规则） | 等价＋范围已退役 |
| 6 | 自审首败（诊断遮蔽超时/跳过清理）修复并保留首败 | `f3537b27` 链独立实现同类语义；PR 分支上的首败证据保留在 PR 会话中 | 等价 |

## 4. 替代实现 SHA

- **`f3537b27c8e1e9515ba4656c44825f05bf4f3a52`**（2026-09-16，“WP-06: retain first-invocation PowerShell failure stages without retries”，main 祖先；其祖先包含本 PR base `f331d71d`——即在同一基线谱系上重做）。
- 后续：`b7f7d226`（2026-09-24，`handoff-first-run-campaign.yml` 预声明捕获战役 + `handoff_campaign_summary.py`）。
- patch-id 实测：PR #41 diff `97f9696b…` ≠ `f3537b27` diff `c3a17eb6…` → 重写，非 cherry-pick。
- 注意：Windows-only 范围退役（2026-09-27 owner 决定）不等于本 PR 已实现——本报告以 `f3537b27`/`b7f7d226` 的实际内容证明取代关系，范围退役仅是补充背景。

## 5. 推荐动作与未解决项

- 内容判定：**全部核心声明＝等价保留（经 `f3537b27` + `b7f7d226`，文件改名重建）；PR #30 PS5.1 根因在 main 上仍声明 OPEN（与 PR 立场一致），Windows 验收义务已按 owner 决定冻结为历史。**
- 推荐：协调者关闭 #41，注明“被 f3537b27/b7f7d226 取代；根因未关闭的开放点转为历史记录（Linux-only 现行平台）”。关闭/留言由协调者执行。
- 未解决项：无 PR 侧待迁移内容。main 上 Windows 相关工作流/测试属历史冻结面，其后续处置属 M3 其他条目，不在本核对内裁定。
