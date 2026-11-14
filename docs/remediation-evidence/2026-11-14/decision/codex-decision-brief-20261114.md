# 决策简报：M0 整改终局处置（2026-11-14）

你是 polymarket-alpha-lab 项目的**决策代理**（gpt-6-astra，思考 max）。项目 owner 已将本轮全部待决事项委托给你裁定（原话："需要做决策的地方你交给本地codex来决定，指定模型时gpt-6-astra/max，全都决策好以后，上传全部代码和交接文档"）。你只在本文列出的选项与参数范围内做决定；无资金/凭据/模型配置/规则修改授权。你可以只读访问本机文件核验证据（只读沙箱）。输出一份结构化决策记录（见末尾格式要求）。

## 项目现状（全部已核验）

- canonical 仓库 wmqfl861/polymarket-alpha-lab：main = `ad001c77a530c156b6ce42ff21b01b8711fd3e2b`（tree bd195335）。链：…→37b28895→C2 9286eefb→C3 6add9b04（合并观察器+PG密钥重试）→ad001c77（diag2 失败当刻取证）。
- 保留分支：`audit/distribution-20261114-bdb39b51` = 7d993df5（distribution 密钥下载重试，已过全部门禁+独立复审，真实 CI run 43583373068 success）；`remed/r03-observer`=156ba4ef、`remed/native-pg-key-download`=a9decad6（均已入 main 历史）；`handoff/m0-review-2026-11-13`=6687ace9（审核交接包）。
- CI 现状（同一 main）：
  - Offline verification run 43590617596：**success**（41,483 passed/122 skipped）。
  - Native project PostgreSQL run 43590617533：**failure**——research(1227)/dispatch(1933)/papersim(92) 全绿；storage 分区证明 311 passed；**"Prove native version switch" 1 failed/65 passed**；aggregate 因 storage 失败。这是该阶段第 4 次连续 CI 失败（C2 自动 43431642963、C2 手动 43453970876、C3 43551531643、ad001c77 43590617533，4/4）。
- R09（同 SHA 双绿）因此阻塞；R10 正式交接文件、Q 回填、外部证据入库均排队在 R09 之后。

## 根因证据链（已闭合至高证据强度）

1. **机制（已证明）**：归档实验 A（零 PG 合成对照，两轮独立复审后执行）：服务端主动关闭 TCP 连接 → 该端口本端留下 TIME_WAIT（Linux ~60s）→ 对同 addr:port 的**无 SO_REUSEADDR bind 精确返回 errno 98**；带 reuse 则成功。客户端先关闭 → 仅 peer 侧 TIME_WAIT，两种 bind 均成功。证据：/home/ubuntu/r03-next-run-20261114-01/control-evidence/report.json（6500B，sha256 b07a4429…）。
2. **失败调用点（代码核验）**：冻结 OLD 基线 2b20002c 的 src/polymarket_alpha_lab/project_postgres/server.py `_start:146`：先执行无 reuse 的 `probe.bind(('127.0.0.1', port))`，再 :149 `pg_ctl start`；失败即 `fail('project_postgres_port_in_use')`，而 files.py:19-20 的 fail() 是 `raise … from None`（主动隐藏原始 OSError 栈——历史日志看不到 bind 位置的原因）。
3. **CI 现场**：4/4 失败均在 OLD initialize→smart stop→stopped 之后 seed 阶段首错 errno=98（C3 捕获）/port_in_use（全部）；diag2 增强（ad001c77）后最新失败的子进程退出快照：任务端口 **local TIME_WAIT=6**（C3 时为 3）、peer 67、OWNER_UNKNOWN。TIME_WAIT 生命周期 ~60s 且 bind 失败与进程退出间隔亚秒——退出快照的 local TW 在 bind 时刻必然在场。
4. **本机对照（2 次真实 OLD 前缀，均通过）**：本机快服务器上 OLD 客户端（psql/pg_ctl）全部主动关闭 → 端口只有 peer 侧 TIME_WAIT（73→88），local 恒空 → bind 成功，seed 全断言通过。证据：/home/ubuntu/r03-next-run-20261114-01/old-evidence-2/report.json（15795B，sha256 2406322b…）。
5. **结论**：冻结 OLD 的无 reuse 端口预检在"自身 init 阶段服务端主动关闭留下 local TIME_WAIT"时误拒自身重启；GitHub runner（慢、2 核）上服务端先关的时序近乎必现（4/4），本机快环境下客户端先关而不复现。这是**冻结 OLD 基线与 CI 环境的真实不兼容**，非测试断言错误。
6. 已知残余缺口（不影响上述结论）：diag2 的链 JSON 被 pytest saferepr 截断（三处 artifact 同文），完整帧链未存档；帧截断方向为最外 8 帧（真实链浅不受影响，docstring 与实现不符——P3）。

## 待决事项

### 决策 1：R03 处置（四选一，可组合）

- **A. seed 前等待端口 local TIME_WAIT 清空**（有界轮询 /proc，上限建议 90s；只在失败前置条件存在时等待）。证明语义：**完全保留原命题**（OLD 在同端口停后可重 init+seed），仅等待内核状态就绪；CI 成本约 +60-90s/次。历史上"等待回收"曾被列为需 owner 批准项——本次批准权即在你。
- **B. seed 阶段换用全新端口**（pick_port 再取一个）。证明语义略弱化：不再是"同端口重入"（端口占用拒绝语义另有专项测试钉住）；CI 零额外时间；但弱化了"stop 后原端口可复用"的隐含覆盖。
- **C. 仅补取证**（父进程在断言前逐字回显子进程 stderr，绕过 pytest 截断，拿完整链 JSON 入档；不解除 R09 阻塞）。可与 A/B 组合为"先取证再修复"或并入同一节点。
- **D. 维持现状**（R09/R10/M1 持续阻塞，OLD 冻结不改、测试不迁就）。
- 背书事实：当前 C3 产品的同路径 `_start` 已带 SO_REUSEADDR（OLD 冻结不可改，否则跨过冻结边界需 owner 亲自处理——不在你的选项内）。

### 决策 2：distribution 修复（7d993df5）并入 main 的时机

- (a) 立即并入（R03 修复节点之前或合并为一次推送）→ 最终交付 SHA 含全部修复，双 CI 只需跑最终 SHA；
- (b) R09 先在"R03 修复版 main"上闭环，distribution 之后单独并入并重跑双 CI；
- (c) 暂不并入（保留分支交付）。
- 约束：并入 main 需该 SHA 上 Offline+Native 双绿才算交付证据；7d993df5 已有自身分支上的 distribution CI success。

### 决策 3：附带小修是否与决策 1 的实施同节点

- diag2 的 P3-1（帧截断保留最外 8 帧 vs docstring 称最内；改为取尾部 8 帧或修正 docstring）与 P3-3（secret-scan 证据日志归档）是否随下一节点一并处理，还是延后。

### 决策 4：参数细节（若你选 A）

- 轮询间隔、总上限、超时后的行为（FAIL 保留首错 vs SKIP 标记）、以及是否在等待前后各记一次端口快照入证据。

## 你的输出格式（严格）

```
DECISION 1: <A|B|C|D|组合> — <一句话理由>
DECISION 2: <a|b|c> — <一句话理由>
DECISION 3: <同节点|延后> — <一句话理由>
DECISION 4: <若适用：间隔/上限/超时行为/快照要求>
RATIONALE: <不超过 300 字的总体推理，含对证明语义与 CI 成本的权衡>
BOUNDARIES CONFIRMED: 冻结 OLD 不改 / 无资金凭据模型规则变更 / 实施仍走 计划→独立复审→红绿→全门禁→聚焦提交→复审→推送→同 SHA 双 CI
```

证据文件（如需核验，均为只读）：本简报所引 SHA/路径与 D:\Projects\pal-remediation-plans-20261113\ 下 q-facts-c3-20261114.md（33,151B，sha256 d536b3ab…）、r03-diag2 计划与证据、/home/ubuntu/r03-next-run-20261114-01/ 一致。不要修改任何文件。
