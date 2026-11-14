# M0 整改正式交接书（R10／D）

> **状态：正式交付书（D）。** 基线＝最终 SHA
> `B=f5ca185a50ad6349275cd79dabd5b701b65a2548`（tree
> `b9c40393a2e2b9f3ad217b9f01545c7788a89b14`），B 上 Offline run **43608957166
> success** 与 Native run **43608957129 success** 双绿（R09 达成）。本文件与其
> 所在文档提交自身的 SHA、其后的 CI／复审结果**不在本文预写**，由提交完成后的
> Git 对象与最终交接回执给出。仓库正本 `wmqfl861/polymarket-alpha-lab`（OD-C）。
> 时间均为 UTC；UNKNOWN 一律保留为 UNKNOWN。本交接书替代仓库外草稿
> `R10-draft.md`（冻结于 C2 blocked 状态）——草稿的历史事实已并入本文，其待补
> 字段按最终事实改写，草稿自身不改。

## 1. 交付范围与完整版本链

原审核对象 `b5ab6108d9e72ee37ce43f8247221f4f674d1224`（审核结论 **VERDICT: FAIL**，
2026-11-12）。本轮整改覆盖 R01–R10、编码前置 E02–E04、离线 fixture 修正 E05、
R07 只读调查、R08 事后补审，以及收尾阶段的 diag2／r03-fix／distribution 三节点。
线上数据库全程零写入（OD-H 不执行）；冻结 OLD 归档 `2b20002c83ee33acb95fb2ca3de841f3e883ebbf`
未改动；不可变交接包 `docs/handoffs/2026-11-12-audit/`、`2026-11-12-m0-execution-review/`、
`2026-11-13-m0-review/` 未改动。

| 标识 | 完整 SHA | 含义与终态 |
| --- | --- | --- |
| 审计基线 B0 | `e8c8a95cd9fea90db02518879e7d30931b5f6926` | 地址增量对比基线（历史锚，非本轮终点） |
| 原 M0 主批次 | `e45c3142eddaf83d59bdda36ffee536e9a25c489` | 五泳道 447 文件单提交；P2-7 偏差保留，不拆写历史 |
| 整改前 main | `37b288956187de404ee0047bc0a5beeccbe9dbf6` | 四处 U+200B 编译／collection 失败（历史） |
| 合并起点 | `fc23fa77b8ec242d3d27f9e0a787d0f63c24cd20` | parents＝37b28895＋delivery `6687ace9446c54b485cdee274f8d57cb54b7ac39` |
| C（首轮候选） | `0eb2a096398c585b8d67a6afcc700420341348e7` | Offline 43404798203 success／Native 43404798264 failure（历史保留） |
| C2（R03 窄修） | `9286eefbd8864a3bf7c5afe146e5e8bd91ceb079` | 两 socket 测试 POSIX occupied-port 证明；CI 双失败（历史保留） |
| 观察者分支 | `156ba4ef813e9fffb511d7ff373073140a5a1361` | OLD seed 首错观察器（并入 C3） |
| PG 密钥重试 | `213e87fc…→a9decad6df26d9d020e6e1dbd0db4b3910c39684` | 官方 PostgreSQL 签名密钥下载有限重试＋fakecurl 测试（并入 C3） |
| C3 | `6add9b041754600109e17e6aa05b0cb99aaface6` | merge(156ba4ef＋a9decad6)，tree `22d2a7b7…`；2026-11-14T03:24:39Z 发布为 canonical main（API 回读 exact，writes=3） |
| ad001c77（diag2） | `ad001c77a530c156b6ce42ff21b01b8711fd3e2b` | 失败当刻取证（`OLD_SEED_FAILURE_MOMENT`）；独立复审 PASS |
| 7d993df5（distribution） | `7d993df58574c0cb713d360334fe352ed591c4a9` | 分支 `audit/distribution-20261114-bdb39b51`；计划（SHA256 `08bda4f4…`）复审 PASS／实施全门禁／代码复审 PASS／分支 CI **43583373068 success**（539 passed，`native distribution: PASS`）／proof 与 kit artifacts 已归档 |
| M | `29a86f642adb6df83c81a2bfff4f18ddd906ef62` | merge --no-ff（双亲 ad001c77＋7d993df5），文件集不相交 |
| A（R03-fix 受审提交） | `8c01798cedf60b7f04346f5d12f6471953db8b28` | parent=ad001c77；fresh 独立代码复审 **PASS（0 P1/P2）** |
| **B（最终交付 SHA）** | **`f5ca185a50ad6349275cd79dabd5b701b65a2548`** | 受审 A 重放（cherry-pick）于 M 之上；tree `b9c40393…`。**A≠B 已登记**：version-switch 测试 blob 与 A 一致、三 distribution 文件 blob 与 7d993df5 一致；diff A..B＝三 distribution 文件、diff M..B＝version-switch 测试文件、diff ad001c77..B＝恰四文件。thin bundle 桥普通 fast-forward 推送（无 force），API 回读一致 |

## 2. 逐节点处置表（原问题 → 处置 → 证据指针）

历史节点（R01–R08／E02–E05）的详细矩阵见已发布
`docs/handoffs/2026-11-12-m0-execution-review.md`、`DELIVERY_PLAN.md` §77 与本
交接书 §4；此处登记终态与收尾三节点全量信息。

| 节点 | 原问题 → 处置 | 集成 SHA（早链） | 证据指针 |
| --- | --- | --- | --- |
| E02/E03/E04 | 37b 的四处 U+200B 编译失败 → 精确删除四个零宽字符，断言语义不动 | `b683948c`／`4fd1ac98`／`6c87eedf` | 各节点独立复审 PASS（§4）；37b 首失败保留 |
| R01 | P1-1 Linux 礼貌间隔测试红灯 → 同一替身时钟控制请求间隔与退避断言 | `a18c8880` | 修后 28 pass；组合 first full 41405/4/122（四 fail 属 E05 fixture 端口，另列） |
| R02 | P1-2 计数钉陈旧／P1-3 uncapped 升级证明被改义 → 恢复历史 67→68 证明常量与 TAIL 迁移 | `bbd2c4fc` | before 1 fail／after 1 pass；dispatch 1933/15 exit 0 |
| R03 | candidate 70/7 与 OLD 63 对齐证明 → 整体重排证明常量 | `53b8481d` | 其后 CI 暴露 socket 端口问题，进入 C2→diag2→fix 链（§3） |
| E05 | 四个 offline 恢复测试共用固定 fixture 端口真实 bind 失败 → 共享合成 state 改用 pick_port＋真实 listener 拒绝→释放→同 archive 恢复证明 | 并入 C `0eb2a096` | 131 passed/0 failed/0 skipped（含 5 项子集）；TOCTOU 边界保留 |
| R04 | 纸面桥三个原生测试仅在 PR Windows 通道 → 本轮实际逐项运行；Linux／直推通道缺口保留 | 与 E04 同 SHA | 3 passed/0 fail（结构化摘要）；M3 补通道（欠项保留） |
| R06 | P3-3 镜像 `-diff`／P3-4 默认体育费率 → 移除 `-diff`、`legacy_scan_fee_category` 限定历史用途、模块 docstring 更正 | `647f9199` | 源码五文件复审 PASS；FX-08 显式类别验收建议由 R05 承接进 §77.7 |
| R07 | P2-3 修改时间矛盾 → 20 条只读 SQL 现状调查 | 无代码提交（结果入 R05 提交） | `DELIVERY_PLAN.md` §77.8；R07-result.json/md 哈希已登记 |
| R05 | P2-1 地址／P2-2 V-6／P2-5 状态板／P2-6 §77／P3-1/P3-2/P3-5/P3-6 等文档修正 | `42116b11` | §77 全部更正＋状态板；独立 spec/code 复审 PASS |
| R08 | P1-4 三旧提交（a93f5fab／15c35a62／b5ab6108）无当时复审 → R02/R03/R04/R05 事后补审覆盖 | 不新增提交 | 历史缺口永久保留，不重建"当时已审" |
| C2 | CI socket errno98 首现 → 两 socket 测试最小 POSIX 证明修正 | `9286eefb` | 复审 PASS（存证 `review-archives/c2-review-696e0ac2.md`）；CI 双失败保留 |
| 观察者＋密钥重试→C3 | version-switch 失败首错不可见／PG 签名密钥 transient-56 → 观察器＋有限重试 | C3 `6add9b04` | C3 发布回执＋CI 回执（入库 `ci-receipts/c3-publication-ci-receipt-99c510e5.json`） |
| distribution | WP-06/FX-07 关联：distribution workflow 签名密钥下载无重试（C2 手动失败时的 exit56 家族）→ 复用已交付有限重试参数，参数化既有测试 | `7d993df5` | 红绿（postgres 9 过／distribution 9 真红→42 全过）；分支 CI 43583373068 success；新增行 secret-scan 0 命中；计划入库 `plans/distribution-retry-final-plan-20261114.md` |
| diag2 | CI 失败当刻端口状态 NOT_EMITTED → 把失败当刻取证最小移植进 shipped 测试（`OLD_SEED_FAILURE_MOMENT`：reason code／有界帧链／任务端口 /proc 计数） | `ad001c77` | 独立复审 PASS（协调者登记）；CI Offline 43590617596 success（41,483/122）／Native 43590617533 failure——首次现场证据 local TIME_WAIT=6／peer 67／OWNER_UNKNOWN；本地门禁（focused 全绿＋`verify_local --full` 41,483/122 exit 0）保全于 Linux 运行侧 `evidence/r03-diag2-20261114/`（库外） |
| r03-fix | 根因裁定后的处置落地：seed 前有界 TIME_WAIT 就绪等待（DECISION 1-A 参数见 §7）＋失败断言前逐字回显子进程 stderr（DECISION 1-C）＋帧截断改保留最内 8 帧（DECISION 3）＋secret-scan 门禁日志归档 | A `8c01798c`→M→B | `r03-fix-evidence/`（9 文件入库）：focused 74/1、`verify_local --full` 41,492/122 exit 0、新增行 312 行 0 命中、`final-registration.md` 登记 A≠B 与重放核对 |
| R09 | 同一最终 SHA 双绿验收 | 在 B 上达成 | `ci-receipts/r09-final-dual-ci-20261114.json`（§3） |
| R10 | 正式交接（本文件 D）＋Q 回填＋证据入库 | 本文档提交（SHA 由回执给出） | §10 |

## 3. CI 失败史与决定性双绿

历史全表（f7aece92 起至 37b28895 共 14 条）已在 `DELIVERY_PLAN.md` §77.5 固定，
此处不重复抄录，仅登记本轮收尾阶段的失败族与终态。

**四次 version-switch 阶段 CI 失败（全部保留为历史，不重跑、不改判）**：

| # | SHA | run id | 失败构成 |
| --- | --- | ---: | --- |
| 1 | C2 `9286eefb` | **43431642963**（push，attempt 1） | 四 Linux 分区全绿（storage 分区 302/2），storage 后续 version-switch 步骤 1 failed／2 passed：OLD seed `project_postgres_port_in_use`、缺 `PAYLOAD_SOURCE_OK`（line 820 断言）；聚合 failure。同 SHA Offline **43431642731 success**（41,411/122/20）分开记录 |
| 2 | C2 `9286eefb` | **43453970876**（唯一授权 manual，attempt 1） | storage 分区 302/2 后 version-switch 同位失败（1 failed/2 passed，18.46s）；research 1227/18；dispatch/papersim 因 PG 签名密钥 curl exit56 NOT_RUN（→ distribution 节点处置）；聚合 failure |
| 3 | C3 `6add9b04` | **43551531643**（push，attempt 1） | storage 分区 311/2 后 version-switch 1 failed／43 passed；观察器首次捕获 `OLD_SEED_FIRST_FAILURE_ERRNO=98`；退出后快照 local TW=3／peer TW=70／OWNER_UNKNOWN；失败当时状态 NOT_EMITTED（pytest 截断）。同 SHA Offline **43551531524 success**（41,461/122/20）分开记录 |
| 4 | ad001c77 | **43590617533**（push，attempt 1） | storage 分区 311 passed 后 version-switch 1 failed／65 passed；diag2 增强：退出快照 local TW=6／peer 67／OWNER_UNKNOWN；链 JSON 被 pytest saferepr 截断（P3，见 §8）。同 SHA Offline **43590617596 success**（41,483/122）分开记录 |

更早的 C Native 43404798264（storage 2 failed＝两占位 bind errno98，302→300 计数差异属
C2 窄修前后）与 §77.5 全部历史（cancelled／编译失败／collection errors 等）同样保留；
cancelled 不因局部 passed 改判，Windows `if:false` 设计性 skip 单列。

**决定性运行（B，2026-11-14，双绿）**：见 §1 与 `DELIVERY_PLAN.md` §77.9——
Offline 43608957166（41,501/122，cleanliness 实际执行）＋ Native 43608957129
（research 1227/18、dispatch 1933/15、papersim 92/0、storage 分区 320/2＋版本切换
**75 passed in 161.86s**＋cleanliness 实际执行＋聚合通过）。决定性等待路径日志
（`ci-receipts/version-switch-proof-b-final.log`，2503B，SHA256
`6d02d989afe20d8f86bf629e08ffe75f32680223529bfae0b245e479ad37dc0d`）：

```text
OLD_SEED_WAIT_BEFORE port=29040 tcp={"local":{"TIME_WAIT":1},"peer":{"TIME_WAIT":72}} …
OLD_SEED_WAIT_AFTER  port=29040 tcp={"local":{},"peer":{}} … elapsed_s=59.099
version-switch native: PASS; old-initialize:74.4s; …; explicit-migration:14.4s
OLD_SEED_WAIT_BEFORE port=40000 tcp={"local":{"TIME_WAIT":1},"peer":{"TIME_WAIT":1}} …
75 passed in 161.86s (0:02:41)
```

端口 29040 首次直接观察 CI 现场的 local TIME_WAIT 残留（此前四次的失败当时状态均
NOT_EMITTED），等待 59.099s 清零后 bind 成功、七阶段证明全过；端口 40000 亦走等待
路径。与 §7 裁定根因闭环。

## 4. 独立复审链（要点）

全部复审均为 fresh、只读、未参与被审改动的独立 reviewer，结论带 `VERDICT:` 行；
作者自审单独标注 self-review，不冒充独立复审。历史节点（E02–E05／R01–R07／R05）
的 reviewer 身份与结论按 `R10-draft.md` §2 矩阵登记（agent_abf72f5b／73b31ae3／
664b3cbf／53d71c52／ddca8def／e1cff483／3348f350／9597b0f9／719039ac／afeb7a69／
a00be9ce／fa6abb2b／696e0ac2 等，均为 PASS；R05 的唯一 P2 经单句修复后复审 PASS；
E05/C 发布前 local-integration review PASS `agent_42ffdac5` 不覆盖其后 CI 失败）。

收尾阶段新增：

| 对象 | 复审结论要点 | 证据指针 |
| --- | --- | --- |
| r03-next 诊断计划 | **PLAN_REVIEW_PASS**（无阻断；P2-1/P2-2/P3 已应用） | `plans/r03-next-diagnostic-plan-20261114.md` 状态行（19,345B，SHA256 `027f877e…`，为驱动脚本 pin 的计划哈希） |
| r03-next 驱动/观察者脚本 | fresh 脚本复审 **PASS（0 P1）**；rev2 应用 P2-1/P2-2/P2-3＋P3-1/P3-4/P3-5/P3-6；rev3 为 scoped delta；实验 A/B 须复审 PASS 后才执行 | `plans/r03-next-tools-MANIFEST.md` |
| diag2 计划与实现 | 独立复审 **PASS**（协调者登记；产物 ad001c77） | 本表＋§2 diag2 行 |
| r03-fix 计划 | REV1 delta 复审 PASS（基于 REV1 的一处误述，见 §8）；REV2/REV3 为授权修正链 | `plans/r03-fix-plan-20261114.md` 状态行 |
| r03-fix 实现（A） | fresh 独立代码复审 **PASS，0 P1/P2**；P3-1（manifest 字段）已更正，P3-2（失败消息措辞）登记不改 | `r03-fix-evidence/final-registration.md` |
| distribution 计划 | 独立计划复审 **PASS**（计划 29,482B，SHA256 `08bda4f4…`） | `plans/distribution-retry-final-plan-20261114.md` |
| distribution 实现 | 实施全门禁（红绿/focused/full/compile/diffcheck/secret）＋独立代码复审 **PASS** | §2 distribution 行；分支 CI 43583373068 |
| owner 委托终局裁定 | 决策代理（gpt-6-astra/max）输出 DECISION 1–4＋RATIONALE＋BOUNDARIES CONFIRMED | `decision/decision-output.log`（67,413B）＋`decision/codex-decision-brief-20261114.md` |
| 旧三份复审全文 | 字节级存证，哈希与定位报告精确一致（提取方法/安全扫描见 README） | `review-archives/`（README＋3 文件） |
| P1-4 三旧提交 | "当时复审"**不存在**（定案）：a93f5fab／15c35a62／b5ab6108 由 R02/R03/R04/R05 事后补审覆盖；历史缺口保留 | `q-basis/archive-locators-20261114.md` §1d、§4 |

本 D 交付书自身：作者自审（self-review，见 §10）；**fresh 独立只读复审由协调者在
本分支推送前派发**，未获 PASS 前不推送（本节点 STOP 于 READY）。

## 5. 七项本地复核逐项终态

| 项 | 终态（2026-11-14） | 剩余边界 |
| --- | --- | --- |
| 1 线上两视图定义与来历 | R07 已完成 20 条只读 SQL（as-of 2026-11-13T05:01:34Z）；11-12 快照语义已核（16/16 复算） | 精确 DDL 时间／操作者 **unknown** 维持；`track_commit_timestamp=off`，11-07—11-12 区间 unverified；FX-09 受管流程后重新登记 |
| 2 服务器运行库及扫描签到 | 服务器 checkout 曾于 2026-11-14 被 distribution 计划只读核对为 HEAD=C3/clean（时间切片，非签到） | **待下一轮扫描**的实际代码签到输出（含代码 SHA 与 clean 标记） |
| 3 镜像清单来源 | **已闭合**：服务器现行树 414/415 逐字节一致（410 原样＋4 脱敏行按 REDACTIONS 原件 hash）；唯一差异＝`intl/wp_intl3/wp_intl_validate.py` 2026-11-14 已记录分页 limit 100→50 修复，差异恰 3 hunk 全为该修复，清单时点字节完整保留于 `.bak-20261114` | 历史 tarball `papersim_mirror.tgz`（`3fff2026…`，1,054,525B）本地与服务器常规路径未找到，**UNKNOWN 如实保留**；现行一致性结论不依赖 tarball（逐文件哈希比对） |
| 4 Windows 历史全量/selfcheck | **全部定位**：五件原件均在 `D:\Projects\pal-untracked-archive-20261112\`（基线 41,332/98 `b0cd56f6…`；合并节点同数 `fba3b1dd…`；基线 selfcheck 前缀 `1a5458b1…` 原件；M0 后 194-export `bd1cd4ec…`；**失败的 `m0_verify.log`（1 failed/41,431/98，exit 1）如实保留**） | 原件为库外 Windows 存档；不重跑 Windows 冒充旧证据，不代替 Linux 验收 |
| 5 Lordakee 副本 tip | `GET repos/Lordakee/polymarket-alpha-lab/branches/main` 与仓库消歧查询均 **HTTP 404**（2026-11-14T08:43:29Z／08:43:55Z，wmqfl861 凭据） | 当前 tip **UNKNOWN**（已删除/转私有/改名不可区分）；历史值 `5bdae2e3`（2026-11-12）保留为时间切片 |
| 6 storage 失败根因 | **已闭环**（相对此前"TIME_WAIT 为推断"）：机制实验 A 证明（服务端主动关闭→本端 local TIME_WAIT→无 reuse bind 精确 errno 98；带 reuse 则成功；客户端先关不产生）＋diag2 现场 local TIME_WAIT 证据＋B 决定性运行等待路径日志，三方一致 | 机制为"机制级证明"，失败当时的完整 OSError 栈在四次历史 run 中仍 NOT_EMITTED（pytest 截断，不可回溯）；本闭环不依赖补拍 |
| 7 两份旧复审原文 | **已存证**：M0 批次（e45c 前身）／合并节点 9e761317／C2 三份全文字节级入库，哈希与覆盖 SHA／发现修复链齐备 | 第四份不存在（P1-4 定案，见 §4 末行） |

## 6. 九项 M0 出口逐项终态

逐项表与证据同 `DELIVERY_PLAN.md` §77.9（单一事实源，此处登记结论行）：

①书面答案：已核，V-8 并入 FX-23 未关闭；②净口径对账：已核（40/41/62 三对象）；
③视图现状/库外复算：已核，DDL 时间 unknown；④镜像/清单/替换表：**关闭**（414/415
现行来源一致；tarball UNKNOWN 保留）；⑤最近扫描代码提交号：**待下一轮扫描**（本
节点入库的 r03-fix 312 新增行与 distribution 新增行 secret-scan 均 0 命中并归档，
属密钥/地址扫描证据，不替代业务扫描轮次）；⑥跨联赛：已接线＋两 caveat＋OD-F 两
附加条件，未真实触发；⑦状态板：Q 已回填终态；⑧原生 DB CI：**关闭**（B 双绿，
Offline 43608957166＋Native 43608957129，四分区/版本切换 75 passed/聚合全过）；
⑨费率/到期方向/只读常量+selfcheck：节点证据维持＋B 的 full local verification
（含 selfcheck 门）实际通过。

**两条 CI 绿不代替外部审计方增量复审、OD-B 归档门、下一轮扫描或统计优势判定；
M0 原始 FAIL（2026-11-13）在增量复审结论到达前不翻转。**

## 7. 根因与处置裁定（owner 委托 codex，2026-11-14）

owner 原话授权："需要做决策的地方你交给本地codex来决定，指定模型时gpt-6-astra/max，
全都决策好以后，上传全部代码和交接文档"。决策代理只读核验证据后输出（原文见
`decision/decision-output.log`）：

- **DECISION 1: A+C**——批准 seed 前有界等待任务端口的 local TIME_WAIT 清空，并在
  同一节点补齐失败断言前逐字回显已捕获 stderr；保留冻结 OLD 的同端口重入证明与
  完整有界诊断，无须先单独跑一轮取证 CI。
- **DECISION 2: a**——distribution 修复 7d993df5 与 R03 修复保持各自聚焦提交，经
  门禁和独立复审后合入同一次 main 推送，以包含全部修复的最终 SHA 取双绿。
- **DECISION 3: 同节点**——P3-1 帧截断改为取尾部（最内 8 帧）；P3-3 同步归档
  secret-scan 门禁实际日志。
- **DECISION 4**——间隔 1s；单调时钟累计上限 90s 不滚动续期；初始 local TW 为零
  立即继续；超时或 /proc 读取/解析不可判定均 FAIL，保留首次失败及诊断，不 SKIP、
  不自动重试 seed、不换端口兜底；等待前后各记一次端口快照；UNKNOWN 不当零。

根因表述（证据链三方闭环）：**冻结 OLD（2b20002c）`server.py _start:146` 的无
SO_REUSEADDR 端口预检，在其自身 init 阶段服务端主动关闭连接留下本端 TIME_WAIT
（Linux ~60s）时误拒自身重启（errno 98 `project_postgres_port_in_use`）；GitHub
runner（慢、2 核）上该时序近乎必现（4/4），本机快环境客户端先关而不复现（对照
NOTREPRODUCED）。这是冻结 OLD 基线与 CI 环境的真实不兼容，非测试断言错误。**
处置为 harness 侧就绪等待（测试语义完全保留原命题），冻结 OLD 与产品源码零改动。

## 8. 偏差与未完成项

**收尾阶段偏差（新登记）**：

1. **REV1 误述链**：r03-fix 计划 REV1 曾误述"现行（diag2）实现已自最内向外收集
   帧并封顶 8"，REV1 的 delta 复审 PASS 基于该误述。实施期首错证据（深栈用例
   12 层调用＋1 捕获帧＝13 帧在红/绿两态均红；实测 frames[0]＝最外测试帧）证明
   diag2 现行实现沿 tb 头→尾（最外→最内）封顶 8、超长链丢弃最内决定帧。该矛盾
   按 REV1 的 P3-4 条款 STOP 上报并获裁定（DECISION 3），实现修改在 REV2 授权后
   进行；REV3 再修正 deque 返回方向与三方文本对齐。全过程保留于
   `plans/r03-fix-plan-20261114.md` 状态行。
2. **diag2 链 JSON 截断（P3）**：diag2 run 的 `OLD_SEED_FAILURE_MOMENT` 链 JSON 被
   pytest saferepr 截断（三处 artifact 同文），失败当时的完整帧链未存档且不可
   回溯；真实链浅不受影响。r03-fix 的逐字回显（DECISION 1-C）与最内 8 帧
   （DECISION 3）为后续防再发处置，不追补历史 run 的截断内容。
3. **P3-2 措辞偏差**：r03-fix 复审 P3-2（失败消息措辞）登记为偏差、无需修改
   （`final-registration.md` 原文 "P3-2 fail-message wording deviation recorded,
   no change required"）。
4. **P3-1 字段更正**：`secret-scan-manifest.json` 的 `scanned_diff_sha256` 字段
   曾误填 added_lines 行的值，final registration 时按 `secret-scan.log` 更正并留
   `correction_note`。
5. **`m0_verify.log` 为失败全量**：Windows 历史五件中 M0 批次后全量是
   **1 failed/41,431 passed/98 skipped，exit 1**（`test_report_tool_pg_mode_is_
   read_only_join`），如实保留，不得写成 M0 后本地全绿。

**保留的历史偏差**（不重演、不复制原文）：24 个 scratch 搬移（非删除）；旧"每周
CI"不是偏差；A 泳道验证码中断与续跑；九文件脱敏与 REDACTIONS 链；镜像曾有
`-diff`；e45c 单大提交（P2-7）；Linux 红灯时推送（P1-1 关联）；旧三提交无当时复审
（P1-4）；旧 C3 读 pg.log 与交接表述冲突（P3-7）；镜像未加日期子目录（P3-8）。
详见 `DELIVERY_PLAN.md` §77.6。

**未完成项（移交清单）**：V-8／P3-10 四 PR 内容级核对（FX-23）；P2-9 win/loss
标签入视图（FX-09）；P3-9 tools 连接守卫覆盖（FX-09）；P3-11 intl 读取上限
（FX-15）；R04 纸面桥 Linux／直推 CI 通道（M3）；下一轮真实扫描及其 `cross_league_
mw_check` 留证＋代码提交号（OD-F）；Lordakee tip UNKNOWN；历史 tarball UNKNOWN；
DDL 时间 unknown；M1 计划复审确认（§9）；OD-B 归档节点（双绿＋增量复审后另开）；
D 文档提交自身的 full/扫描/CI 由推送后回执承载。

## 9. M1 启动门状态

`M1-next-nodes-plan.md`（28,092B，SHA256 `0a48b7bc…`）登记的启动门：R09/R10 正式
handback 齐全、交还最终源 SHA、最终同一 SHA 双绿（四 Linux 分区＋storage 版本
切换＋聚合）——**技术条件已随 B 双绿与本 handback 满足，启动门解锁**。两点如实
保留：该计划文件头自记"首轮 reviewer FAIL 后修复五项发现，待同一 reviewer 复审"，
其独立复审 PASS 与否须以复审回执为准（本交接书不代填）；实施由 owner／协调者
派发，FX-18 归档须另有外部增量 review PASS，不搭双绿便车。真实资金、凭据、真实
下单仍须 owner 单独明确确认。

## 10. 证据入库与复核入口

**分支**：`docs/r10-final-20261114`（基于 B；本节点三个聚焦提交：证据入库／Q 回填
／D 交付书）。**不推送**：待协调者派发 fresh 独立只读复审（Project Iron Rule 4，
`VERDICT: PASS`）后由协调者推送。

**证据目录**：`docs/remediation-evidence/2026-11-14/`，33 文件＋`MANIFEST.md`
（逐文件 bytes/SHA256；敏感扫描 0 公网 IP、0 凭据值，无脱敏改写；`diag2-native-runs`
与 `release-and-ci` 无独立回执文件，事实由决策简报与 r09 回执承载，见 MANIFEST §3）。

**复核要点（给增量复审者）**：

1. 版本链：`git log --format='%H %P %T %s'` 核对 §1 各 SHA 与双亲；`git diff
   --stat A..B`＝三 distribution 文件、`M..B`＝version-switch 测试文件。
2. 双 CI：按 `https://github.com/wmqfl861/polymarket-alpha-lab/actions/runs/
   43608957166` 与 `/43608957129` 核对 attempt/head/jobs/steps 与 §3 计数。
3. 证据哈希：对照 `docs/remediation-evidence/2026-11-14/MANIFEST.md` 逐文件复算。
4. 不重复已完成工作：R01–R08 已审节点不返工；四次历史失败不重跑；本分支仅三个
   写域（`DELIVERY_PLAN.md`、本文件、证据目录），无产品/测试/workflow 改动。
5. 停止条件：任何哈希不符、head/jobs 不符、或发现未登记偏差，停止通过声明并保
   留事实。

**D 自身后发生事实**（本提交推送后的 Offline/Native CI、最终 SHA/URL/回执）由
协调者的最终交接回执登记，不回写本文、不为记录自身 CI 生成后续提交。
