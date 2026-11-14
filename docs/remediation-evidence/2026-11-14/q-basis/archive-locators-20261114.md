# 取证定位清单：七项本地复核 + R08 补链（2026-11-14）

只读取证 worker 输出。不改动 repo tracked 文件；本文件为唯一写入。
定位规则：找到=路径+字节+SHA256+关键内容摘录；未找到=UNKNOWN+已查位置。
Agent transcript 输出按任务规则仅作**线索级**定位（标注 [线索级]），正式存证需另行提取归档。
gh api 仅用 GET；服务器地址/端口与既有 REDACTIONS 口径一致（SERVER_HOST_REDACTED）。

## 1. 两份旧复审全文（七项复核第7条）

### 1a. M0 批次 e45c3142 复审原文 — [线索级·已定位]
- 路径：`C:\Users\Administrator\.zcode\cli\agents\sess_11088027-b2d9-4036-8874-9517cc5eba70\agent_5c3c054d-5138-461a-a83e-2b280f20c5ec\output.txt`
- 字节：7056 B（30 行）；SHA256：`101e8ef4ed469f577f651202db3236d4775f59da0cc66dc47e3ca170c7c69fa7`
- agent 创建时间 2026-11-12T14:13:27Z（metadata.json），描述 "Review M0 swimlane batch"
- 覆盖：`D:\Projects\polymarket-alpha-lab @ 9e761317 + uncommitted batch`（即入库前的 M0 批次，后成为 `e45c3142eddaf83d59bdda36ffee536e9a25c489`）；fix-list A-G 逐项核验
- 发现：**1 P2**（REDACTIONS.md 中 MANIFEST.sha256 脱敏哈希行不验：记录 `c84f65ff…` ≠ 实际 `1678ca08…`，其余 8 行全验、415 内行全验）+ 3 P3（conservative_edges 注解漏 TerminalYesProbability；§73 无就地更正；load_rows_pg 未关连接）
- 修复链：P2 → REDACTIONS.md 带日期注记修正（C3 内可见 `## Note (2026-11-12, review P2 fix)`）
- 结尾：`VERDICT: PASS`
- 与交付书摘要一致（`docs/handoffs/2026-11-12-m0-execution-review.md` §2.3 "1 P2 + 3 P3 全部修复后入库；P2 = 脱敏台账自身哈希行的先后问题"）

### 1b. 合并节点 9e761317 复审原文 — [线索级·已定位]（交付书"两份复审"的第一份）
- 路径：`C:\Users\Administrator\.zcode\cli\agents\sess_11088027-b2d9-4036-8874-9517cc5eba70\agent_716a2ea3-16bc-4ed5-aad1-ea8fdef1a4f4\output.txt`
- 字节：8704 B（57 行）；SHA256：`f6f202642b3ce6000e1604315e87cbe8dcbbf6cbc69d03bf5c3a302fcda1efa7`
- agent 创建时间 2026-11-12T11:42:26Z，描述 "Review audit handoff merge"
- 覆盖：merge `9e761317`、审计基线 `e8c8a95c`、delivery `8531ebcf`、分支 `handoff/audit-2026-11-12`；18 manifest blob 独立重哈希；41,332/98 算术逐项复验
- 发现：0 P0-P2 + 3 P3（+52 tests 实为 47 实例；请求分支名缩写；Lordakee 不可达提示）
- 结尾：`VERDICT: PASS`

### 1c. C2 9286eefb 复审原文 — [线索级·已定位]
- 路径：`C:\Users\Administrator\.zcode\cli\agents\sess_11088027-b2d9-4036-8874-9517cc5eba70\agent_696e0ac2-4b64-4cc9-b067-59f1e5c93bbf\output.txt`
- 字节：1999 B（10 行）；SHA256：`86093b01f81ea4211ab333898c99c88168b29e3131531fed11ac79083c076e3f`
- 覆盖：C2=`9286eefbd8864a3bf7c5afe146e5e8bd91ceb079`（parent C=`0eb2a096…`，tree=`7d81cdb4…`；committed diff 与已审 1530B patch 逐字节一致）；C2 唯一本地 full `C2-full-egh34u7z` 41411/122/20w exit0
- 范围限定原文："仅限固定 C→C2 提交一致性、机械证据及这一次 C2 本地 full 验收；不代表 C2 CI green"
- 结尾：`VERDICT: PASS`

### 1d. 补丁轮 a93f5fab / 15c35a62 / 37b28895 的"原复审" — **不存在（P1-4 已定案）**
- 不可变审阅报告第 104 行原文：`P1-4 a93f5fab、15c35a62、b5ab6108 三个提交没有复审记录`（见 §4 的 01-review-report.md 定位）
- 闭环方式 = 事后补审：R02/R03/R04 覆盖 a93/15c 全部相关改动、R05 覆盖 b5（登记于 R10-draft.md §2 R08 行 + §3 P1-4 行）；历史缺口保留，不重建"当时已审"

结论：三份可定位复审均在当前 ZCode 会话 transcript（会话根 `sess_11088027`，2026-09-07 创建，471 个 agent 目录，三份 output.txt 均完好）。已查未发现其他副本：全部 `.zcode/cli/agents`（62 会话）grep `e45c3142`/`9e761317` 仅命中本会话；`.claude/projects` 无本项目目录；`.codex/sessions` 无 11-12 复审产物；`pal-remediation-plans-20261113`、repo docs、`pal-m0-startup-*`、`pal-untracked-archive-*` 无全文。**正式发布需协调者从上述路径提取归档（建议随 R10 交付，给出提取后的 bytes/SHA256）。**

## 2. 旧 Windows 历史 full/selfcheck 日志与完整 hash（七项复核第4条）— 全部找到

目录：`D:\Projects\pal-untracked-archive-20261112\`

| 文件 | bytes | SHA256 | 关键内容 |
| --- | ---: | --- | --- |
| `baseline_verify_20261112_024250.log` | 57355 | `b0cd56f66dea3229940190fe7745bc8a3262a5db5f322c9b9cad2d368c559688` | 基线全量：L685 `41332 passed, 98 skipped in 3390.23s`；L686-688 `PASS: full pytest` / `PASS: full local verification` |
| `merge_node_verify.log` | 57355 | `fba3b1dd062b3bcd717c3da27a35a0c5062ec45bccd8a3f00d4b38c157138297` | 合并节点 9e761317 全量：同 `41332 passed, 98 skipped in 3105.40s`，PASS |
| `selfcheck_baseline_20261112.txt` | 1635 | `1a5458b13907e733e894fae2eb713588458eafb07b4b18b63bc1bd2da24f5e75` | **基线锚 `1a5458b1` 前缀原件**：`173 package exports`、`selfcheck: PASS (10/10 checks)` |
| `selfcheck_M0_20261112.txt` | 1635 | `bd1cd4ec087b22f86f2d94a760b2bf6a157a2ab4e7327da5c6a7e1dead32d051` | **M0 后 194-export**：`194 package exports`、10/10 PASS；与基线仅导出计数行不同（复审 F 项口径一致） |
| `m0_verify.log` | 60447 | `fabb5f3a0e03ef3145a501e2236130a50d26ddee0fc3ac6e78d75188d3e993da` | M0 批次后全量：L760-762 `FAILED tests/test_papersim_ledger.py::test_report_tool_pg_mode_is_read_only_join`；`1 failed, 41431 passed, 98 skipped in 3344.30s`；`FAILED: full pytest (exit 1)` |

注意：`m0_verify.log` 是**失败**的全量（exit 1，上述单测），如实保留，不得写成 M0 后本地全绿。第4条的"原完整存档未证"缺口可由上表关闭（原件+完整 SHA256 均在）。

## 3. Lordakee origin 当前 tip（七项复核第5条）— 404，tip UNKNOWN

- 认证身份：`gh api user` → `wmqfl861`
- `GET repos/Lordakee/polymarket-alpha-lab/branches/main` → **HTTP 404 Not Found**，观测 UTC `2026-11-14T08:43:29Z`（单次，未重试）
- 消歧（一次性补充 GET）：`GET repos/Lordakee/polymarket-alpha-lab` → **HTTP 404**，UTC `2026-11-14T08:43:55Z`
- 结论：该仓库对 wmqfl861 凭据不可见（已删除/转私有/改名之一，无法区分）；**当前 tip = UNKNOWN**，非瞬时网络故障。历史值仍为 `5bdae2e3`（V-4，2026-11-12）。本地 remote 名 `origin`=Lordakee、`fork`=wmqfl861、`srv`=服务器（host 脱敏，同 REDACTIONS 服务器）。

## 4. R08 补链：a93f5fab / 15c35a62 / b5ab6108 — **可发布定位，无需重建**

### 4a. 已发布（repo 不可变包，GitHub-first 成立）
- `docs/handoffs/2026-11-13-m0-review/evidence/ci_runs.txt` @ delivery `6687ace9446c54b485cdee274f8d57cb54b7ac39`（同内容亦在合并 `fc23fa77…`）
  - blob `61c9845828786502a889226e2c67da409db67b0b`；8493 B；SHA256 `91792b8760f2e518a5f80fad7057bc890dacda641a3d50e36c65537c5c9168f8`
  - 采集窗口注明 "between about 23:30Z on 2026-11-12 and 00:45Z on 2026-11-13"
- `docs/handoffs/2026-11-13-m0-review/01-review-report.md` @ 同 delivery：blob `0c39d873a19e3ec61219dc5375e33aa6c1f54140`；20035 B；SHA256 `771a8833bf587c18938a7ec148940fa72619deda1abd447f8899043a6763dfb0`；L104 P1-4 原文；L258 `VERDICT: FAIL`（被审终点 b5ab6108 的原审通知）

### 4b. 三轮 CI run 编号与结论（ci_runs.txt 原文数字）
| 被审 SHA | run id | workflow/event | 结论 |
| --- | ---: | --- | --- |
| a93f5fab | 43250132444 | Offline/push | cancelled |
| a93f5fab | 43250132456 | Native/push | cancelled |
| 15c35a62 | 43250257520 | Offline/push | cancelled |
| 15c35a62 | 43250257695 | Native/push | **failure**：dispatch 5 fail（`assert '70' == '68'` 类计数钉）；storage 2 fail = `test_project_postgres_native.py:188`、`test_project_postgres_backup_native.py:90` 均 `OSError: [Errno 98] Address already in use`；version step skipped |
| b5ab6108 | 43250580628 | Offline/push | **failure**：`tests/test_papersim_intl_data.py::test_fetch_politeness_and_retry`（P1-1，断言 `assert ([5.0, 1.9999816629999714] and False)`）；1 failed/41407 passed/122 skipped |
| b5ab6108 | 无匹配 | Native/精确SHA | ci_runs.txt 记录无匹配 run（不推原因） |
| （前史）e45c3142 | 43245367343 / 43245367334 / 43245420705 | Native/push、Offline/push、Native/dispatch | cancelled / failure / failure(dispatch5+storage2) |

注：15c35a62 storage 两处 errno98 与后来 C/C2 CI 失败同路径（`native.py:188`、`backup_native.py:90`），是 R09 阻塞问题的最早 CI 现场记录。

### 4c. 本地原始 run 证据（未发布、可随需归档）
`D:\Projects\pal-remediation-ci-evidence-20261113\evidence\`
- `ci-evidence.json` 252192 B，SHA256 `af05772d093d7f0da610b579a6467a54822019449be68bf483b048038b9e3308`（与 R10-draft §8 记录值一致）
- `run_43250132444.json` 4288 B `255246020bfcd8e0c4a53042b2db5849853b5dc07572f1c6bcb40f11a3d53ef3`
- `run_43250132456.json` 21236 B `9a13cfa83af68f312e6e768a58eb0a7b509a0888f92da6d993008f97d1f0df97`
- `run_43250257520.json` 4288 B `41c2f30dfb6f1c7af26a08f9938a885a0bba64f7c831376dd890262a3a67d88b`
- `run_43250257695.json` 21221 B `85d873b80e8d8fbbbdb0e55fea50e83a01b59ef05911117be3a77665d4ef7660`
- `run_43250580628.json` 4282 B `5dd602e4d9c01f5b29aad4b774f2c994d541b7fb57f5ae27b2867dc81d54aaa7`
- 另有同名 `run_*_logs/`（log_000N.txt + index.json）与 details/jobs/stdout 文件

### 4d. 发现闭环记录定位
- P1-4（三轮无复审）→ 事后补审：`D:\Projects\pal-remediation-plans-20261113\R10-draft.md` §2 表 R08 行 + §3 表 P1-4 行（R02/R03/R04 覆盖 a93/15c、R05 覆盖 b5；"属事后补审，原历史缺口保留"）
- P1-1（礼貌间隔）→ R01（同文件 §3 首行）
- 结论：R08 证据链**已具备可发布定位**（4a 为 repo 内固定 blob；4c 为本地原始件）；唯一不存在的是 a93/15c 的"当时复审"，按 P1-4 定案为永久历史缺口，勿伪造重建。

## 5. 镜像服务器来源证据（七项复核第3条）— 本地一致已证；来源证据缺口**确认存在**

C3 = `6add9b041754600109e17e6aa05b0cb99aaface6`（本地 repo 有对象，canonical wmqfl861 main）

### 5a. C3 内现值
- `docs/paper-sim/server-mirror/MANIFEST.sha256`：49851 B；**415 条哈希行**（`grep -cE '^[0-9a-f]{64}'` = 415；头注 "411 行与服务器逐字节一致，4 行已脱敏"）；git blob `2e85e0bbad2d0dd621723bb248da58806be7b5d7`；文件 SHA256 `37fac2e0416deaf314acd0547d32157d3f62e3652d9c44e0fd611c8471a1862b`
- `docs/paper-sim/server-mirror/REDACTIONS.md`：2801 B；git blob `17857616e6764cb055ad2cc873db1f3baa337cd3`；SHA256 `7387646ae6492f237b47a23cb3f0a323dd1bc661437cf60bdc3ca6611d410ec2`；**九行齐全现值**：
  VIEW-DIFF.md `a7f5cc36…`→`a1b8e595…`；FX-04-wiring-proof.md `dce4f44a…`→`7e949434…`；MANIFEST-NOT-MIRRORED.md `d635c6fb…`→`935db2c9…`；**MANIFEST.sha256 原值列= `edited-in-place-post-redaction (see note)`、现值=`37fac2e0…`**；VERSION-CHECKIN.md `93efb8a7…`→`1a6caa94…`；league_strength.py `d76b25e8…`→`1733bbd9…`；write_scan.py `93ed8a73…`→`9d078a8c…`；eredivisie_validate.py `4f58c43b…`→`2d867758…`；fotmob_validate.py `6e8be5cf…`→`d0e049f3…`；含 `Note (2026-11-12, review P2 fix)` 与 `Current-value refresh (R05, 2026-11-13)` 两段注记
- 头注来源声明（MANIFEST.sha256 L2-6）：`Source host: ubuntu@SERVER_HOST_REDACTED (ser223321960800), tree ~/paper-sim`；inventory `2026-11-12T13:04:44Z..13:30:00Z (UTC)`；`manifest rows generated server-side at mirror time`；`Mirror archive: papersim_mirror.tgz sha256 3fff20269ac6edfcaaf151e47e9dd5fcb3eae9b2b1846f710cb0bd2266ed5983 (1054525 bytes)`

### 5b. "确实来自服务器"的原始采集证据 — **本地 UNKNOWN（缺口确认）**
- `papersim_mirror.tgz`（sha256 `3fff2026…`，1054525 B）本地**未找到**。已查：`D:\Projects\pal-m0-startup-20261113-y2xt2b7x\`（transfers 仅两个 git bundle；mirrors 仅复审文档）、`D:\Projects\polymarket-alpha-lab\.scratch\`、`D:\Projects\pal-remediation-plans-20261113\`、`C:\Users\Administrator` 顶层、C3 git 树（无 tgz 类对象）
- 亦无独立的服务器侧回执/签名（仅 MANIFEST 头注自我声明 + REDACTIONS "original bytes remain on the server"）
- 结论：与 R10-draft 七项第3条一致——"本地一致不证明来源"；若要闭合，需 owner 授权从服务器取回 `papersim_mirror.tgz`（或服务器端重算 415 行+九原件哈希）作为来源证据；本地无物可标记，勿以头注冒充独立来源证明。

## READY

本报告：`D:\Projects\pal-remediation-plans-20261113\archive-locators-20261114.md`（新建，写前已确认不存在）
SHA256（本文件）：见交付回执（写入后由协调者计算或要求本 worker 补算）。
