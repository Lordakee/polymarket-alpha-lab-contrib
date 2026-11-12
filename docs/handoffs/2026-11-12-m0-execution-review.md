# 交接：2026-11-12 审计交接包的 M0 执行，请审核（给审核 agent）

本文件是 `docs/handoffs/2026-11-12-audit/` 审计交接包的执行交付书，供下一轮独立审核。
执行者：ZCode 协调者（本地 agent），授权来源：owner 交付审计交接包的消息（原话见
`DELIVERY_PLAN.md` §77 首段）。全程遵守 AGENTS.md；与 AGENTS.md 的四处张力已在 §77.2
报告，未自行处置。

## 1. 固定版本（校验起点）

| 项 | 值 |
| --- | --- |
| 仓库 | `https://github.com/wmqfl861/polymarket-alpha-lab`，分支 `main` |
| 审计基线 | `e8c8a95cd9fea90db02518879e7d30931b5f6926`（交接包指定） |
| 交接包合并 | `9e761317131ab0e6197f0fc4f8e72c828eccd016`（merge，docs-only 21 文件） |
| **M0 主批次** | **`e45c3142`**（泳道 A-E + 门面 + 脱敏 + gitattributes，447 文件） |
| 计数钉补修 | `a93f5fab`（9 个原生测试文件 68→70 + TAIL）、`15c35a62`（余 2 个） |
| Lordakee 侧 | 停在 `5bdae2e3`（V-4 实测落后；OD-C 待决，未动） |

基线校验锚：执行前 selfcheck 完整输出存档 sha256 前缀 `1a5458b1`；合并树全量
`41,332 passed / 98 skipped / 0 failed`（= 审计 CI 41,262/121 + WP-INTL 47 实例 +
23 个 Windows 独有项，该算术已由复审逐项验证）。M0 批次后 selfcheck 仅导出计数行
变化（173→194），锚点逐字节不变（复审 F 项确认）。

## 2. 执行了什么

### 2.1 交接包核验与合并（步骤 0）
§3 校验脚本原样运行，输出逐字符合预期；本地合并后过全量验证 + 独立复审
（VERDICT PASS，0 P0-P2）再推送。复审确认交接包全部内部数字可复算、evidence
脚本只读、21 文件零秘密零公网地址；提交后修订 e84c36ea（仅新增 05 提示词）为良性。

### 2.2 九项只读核实（V-1..V-9，步骤 2）
完整结论与证据在 `DELIVERY_PLAN.md` §77.1。要点：
- V-1 跨联赛接线：**已接线**（scan40/41/43/44 实证；正式证明在
  `docs/paper-sim/server-mirror/FX-04-wiring-proof.md`，file:line + sha256）。
- V-2 视图：**线上已是修复版**——C3 泳道用迁移 #70 的逻辑在库外复算 16/16 行
  逐分吻合证明。这**修正了审计 P-3 的前提**（审计认为库里仍是坏视图），
  OD-H 因此降级为卫生操作。
- V-4 两仓库不同提交；V-5 V1 管线零使用；V-9 paper_sim 在独立集群（nix postgres
  :55432，仅 1 业务库），与 V1 的 PG18/5433 分开。
- V-6 账本重算：审计期 +23.3% 为重复计账虚高（真实 +17.8% 毛/+15.2% 净）；
  当前全量 62 结算 +23.3% 毛/**+20.7% 净**（费后），bootstrap CI −4.9..+47.0，
  最大单一市场占净盈亏 37.6%——样本仍不足以宣称优势。工具与证据：
  `tools/papersim_ledger_report.py`（10-30 快照复算 +23.30% 毛/+20.61% 净，落在
  fix-list 验收带 20-21% 内）；`~/paper-sim/review/audit2026_v6_v7/`（服务器）。
- V-7 xG 源分离：FotMob=Understat×0.90-0.95 跨源尺度差真实存在；但 2026/27
  联赛上升在纯 Understat 源内亦现（+4~25%）——审计机制对、示例方向反。

### 2.3 M0 五泳道（步骤 4）
| 泳道 | 内容 | 位置 |
| --- | --- | --- |
| A 费用 | FX-06 费率表（12 官方值实时复核）；FX-01 净口径账本+报告脚本；FX-14 gates 只读化 + 测试 847 行修复 | `papersim/fees.py`、`ledger.py`、`gates.py`、`tools/papersim_ledger_report.py` |
| B 加密 | FX-13 到期方向显式化（下方逐位不变/上方精确补集）；FX-14 VOL_WINDOW_BARS 只读 | `papersim/crypto_model.py` |
| C 服务器 | FX-03 镜像 415 脚本+清单；FX-04 接线证明；FX-02 只读段（快照+VIEW-DIFF） | `docs/paper-sim/server-mirror/`、`ledger-snapshots/2026-11-12/` |
| D 工程 | FX-07 触发器+papersim 分区+即弃集群（零凭据）；FX-22 SyntaxWarning 即失败 | `.github/workflows/native-postgres.yml`、`pyproject.toml` |
| E 文档 | FX-05 状态板+§77+§69/73 追加更正+usage/docstring 现状化+README 指针 | `DELIVERY_PLAN.md` 顶部与 §77、`README.md`、`usage.md` |

M0 批次独立复审 VERDICT PASS（1 P2 + 3 P3 全部修复后入库；P2 = 脱敏台账自身
哈希行的先后问题，已带日期注记修正）。

### 2.4 CI（FX-07 验收）
- 运行 `43245420705`（手动）：**失败**——根因是 9 个原生分区测试的**陈旧迁移计数钉
  （68）**：该 workflow 自 #69/#70 迁移落地后从未运行（这正是审计 FX-07 的发现），
  复活即暴露。非 M0 批次缺陷；修复 = 钉更新 68→70 + manifest TAIL 常量
  （`a93f5fab`+`15c35a62`，共 11 处、9 文件，与 WP-P4 时代的 69→70 同类）。
- push 触发 `43245367343` 被并发组取消（预期）；钉修复后的自动触发运行见
  Actions 页（`a93f5fab` 起）。**最终绿否待确认**——若仍失败，请本地 agent 按
  运行日志继续排查（判断标准同上：先分辨"暴露的陈旧钉"与"真缺陷"）。

### 2.5 执行偏差（全部透明记录，§77 亦有）
1. 工作区 24 个未跟踪临时文件使 §3 脚本首步拒绝 → 全部**搬移**（非删除）到仓库外
   `pal-untracked-archive-20261112/`（24 项 ls -a 验证完整），脚本原样重跑通过。
2. CI schedule 按 fix-list 用**每周**（`17 4 * * 1`）而非交接提示词的"每日"——
   fix-list 明说私有仓库配额不要每天跑；要改是一行。
3. A 泳道代理因平台验证码超时中断 → 磁盘工作完好，续跑收尾（无返工）。
4. 镜像树 9 文件含运行服务器地址 → 占位符脱敏 + `REDACTIONS.md` 记录
   原始↔脱敏哈希（合规优先于字节保真；服务器原件仍在）。
5. `.gitattributes` 把镜像树标 `-text -whitespace`（防 EOL 转换破坏哈希保真）。

## 3. 审核建议核对项（给审核 agent）

1. 合并节点与 M0 批次的两份复审是否尽责（可抽查其引用的 file:line）。
2. 净口径数字：用 `tools/papersim_ledger_report.py` 跑
   `docs/paper-sim/review-2026-10-30/settled_ledger.json`，应复现 +23.30% 毛 /
   +20.61% 净（fix-list FX-01 验收带）；再跑 `docs/paper-sim/ledger-snapshots/
   2026-11-12/` 的 CSV，应得 V-6 当前数字。
3. FX-04 接线证明的引用是否与镜像内 scan44.py 实际行号一致（复审已抽验 2 处）。
4. 脱敏完备性：`grep -r "<服务器地址>" docs/` 应为零命中；REDACTIONS.md 9 行全验证。
5. 冻结不变量：4 闸门阈值、10 变体、selfcheck 10 项、夹具——抽查 diff。
6. 测试无弱化：复审的"removed-line scan"结论可复验（重点
   `tests/test_native_postgres_workflow.py` 的重构是加强）。
7. **服务器侧事项无法由云端审核完成**（与上轮审计相同限制）：V-2/V-3/V-6/V-7 的
   服务器证据已镜像/快照进仓库，可查；但"线上库当前状态"需本地 agent 复核。

## 4. 需要 owner 的决策（OD-A..H，已一次性提交，未答复按保守默认）

| 项 | 决定什么 | 推荐 | 默认 | 核实数据支持 |
| --- | --- | --- | --- | --- |
| OD-A | V1 冻结 vs 激活 | ① 冻结 | 不动 V1 | V-5：零使用记录 |
| OD-B | 231 万行不可达代码 | ① 打标签归档 | ③ 不动 | 复审确认数字 |
| OD-C | 仓库正本 | ① wmqfl861 | 记录两边 | V-4：Lordakee 落后 |
| OD-D | 账本 v2 | ① 批准 | ② 仅加列 | V-9+V-6 |
| OD-E | 规则写进 AGENTS.md | ① 写入 | ② 计划内约定 | §77.2 张力清单 |
| OD-F | 跨联赛 MW 恢复前提 | ① 书面证据 | ① | V-1+C2 已满足① |
| OD-G | 晋级/暂停规则 | ① 批准 | 不启用 | V-6 CI 跨零 |
| OD-H | 视图修复应用 | ~~① 应用~~ **前提已失效**：C3 证实线上已是修复版；选①=无害卫生操作，选②=维持现状 | ② | V-2/C3 |

另需 owner 帮助：无阻塞性请求。CI 若钉修复后仍失败，可能需要本地 agent 排查
（云审核无法跑带 PG service 的 workflow）。

## 5. 未完成/在途事项（非本次执行缺口）

- CI 最终绿否待确认（见 §2.4）；绿后把运行号记入 §77（M0 出口第 8 项）。
- M1（FX-08/09/10/11/12）与 M2（FX-15/16/17）未开始——按计划在 M0 出口后；
  OD-D/OD-G 影响其细节。
- M3 并行项中不依赖决策的（FX-20 根包按需导入、FX-22 其余、FX-24）未启动。
- 交易面（不受审计影响）：ETH-2000 双仓贴屏障 ~0.6% 待结算；11/14-17 欧国联
  影子首验；11/19-20 联赛复赛扫描（新 κ 表首战）；11/22 起 MD5 欧战扫描
  （跨联赛 MW 按 OD-F① 条件恢复）。

## 6. 审核所需的本地命令（仓库根，bash）

```bash
git fetch origin main && git log --oneline -5 origin/main   # 应见 15c35a62..e45c3142..9e761317
git show e45c3142 --stat | tail -3                          # 447 files, M0 batch
grep -rn "154\.89\.153\.24" docs/ | wc -l                   # 期望 0（脱敏完备）
# 净口径复算（fix-list FX-01 验收带 20-21%）：
.venv/bin/python tools/papersim_ledger_report.py --ledger-json docs/paper-sim/review-2026-10-30/settled_ledger.json
# 当前账本（CSV 模式）：
.venv/bin/python tools/papersim_ledger_report.py --decisions-csv docs/paper-sim/ledger-snapshots/2026-11-12/decisions.csv --resolutions-csv docs/paper-sim/ledger-snapshots/2026-11-12/resolutions.csv
.venv/bin/python -m polymarket_alpha_lab.papersim.cli selfcheck   # PASS 10/10；导出行 194
```
