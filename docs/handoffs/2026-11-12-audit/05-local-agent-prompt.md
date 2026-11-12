# 05 给本地代理的提示词

"提示词正文"一节可以整段复制给本地代理（项目的协调者）。它是自包含的：目标、不要重复的工作、
固定版本、允许与禁止、环境、步骤、验收、失败处理、要返回的证据都在里面。

固定值：

| 项目 | 值 |
| --- | --- |
| 仓库 | `https://github.com/wmqfl861/polymarket-alpha-lab` |
| 交付分支（保留，不删） | `handoff/audit-2026-11-12` |
| 审核基线 | `e8c8a95cd9fea90db02518879e7d30931b5f6926`（`main`，2026-11-11） |
| 交付提交（文档、证据、清单） | `8531ebcfb0e7c76b36ad93238a7a7282676beefc` |
| 交付目录 | `docs/handoffs/2026-11-12-audit/`，在交付提交里共 20 个文件，目录的 git 树对象 `f9f74f79056a7cf98980afff5961d44f469a67f2` |
| 清单文件 | `docs/handoffs/2026-11-12-audit/MANIFEST.sha256`，2316 字节，19 行，SHA-256 `c720ad8c9f472f0ba023515badf18d4b0ea8abaf007d308ba2a013a10e3b19be` |
| 固定网址（需要登录） | <https://github.com/wmqfl861/polymarket-alpha-lab/tree/8531ebcfb0e7c76b36ad93238a7a7282676beefc/docs/handoffs/2026-11-12-audit> |

`MANIFEST.sha256` 逐行列出除它自己以外的 19 个文件的 SHA-256（包括
`MANIFEST.json`，后者另外记录了每个文件的字节数）。本文件在交付提交之后的下一个提交里，不在清单
的覆盖范围内。交付分支上还有一个更早的草稿提交 `2262d2eb`，已被交付提交取代，不要使用。

---

## 提示词正文

你是 polymarket-alpha-lab 项目的协调者。请按仓库里 2026-11-12 的审核交接包执行修改和开发。
全程遵守仓库根目录 `AGENTS.md` 的现行规则；本提示词或交接包与 `AGENTS.md` 冲突时，以
`AGENTS.md` 为准，并把冲突报告给我。

### 1. 目标

1. 核对交接包的完整性，把它合入 `main`。
2. 完成九项只读核实（V-1 至 V-9），把八项待决事项（OD-A 至 OD-H）一次性提交给我。
3. 完成里程碑 M0（口径与基线），然后按计划继续 M1、M2；M3 与它们并行。
4. 每个节点都走完整流程：计划、实现、验证、本地提交、独立只读复审、推送、记录。

### 2. 已经完成、不要重复的工作

- 全仓库审核已经做完，结论和证据都在交接包里，并经过一次独立只读复审（`VERDICT: PASS`）。
  不要重新做全量审计；只在动手前复核你要改的那几处。
- "手续费计入入场闸门"已在 11-05 完成（`papersim/gates.py` 的 `_apply_fee_and_haircut`）。
- 11-07 模型评审的第 4、5、6、8 条已经修复并在当前代码里。
- **2026-11-11 的审核和它的交接已被我作废并移除。不要执行其中任何条目，特别是不要修改
  `tools/analysis/codequality.py`。**
- 交接包没有修改任何项目代码，只新增了 `docs/handoffs/2026-11-12-audit/` 这一个目录。
- D1、D2、D3（本地代理、研究数据、首轮不设金额上限）早已决定，不要再问我。

### 3. 固定版本与完整性校验

| 项目 | 值 |
| --- | --- |
| 仓库 | `https://github.com/wmqfl861/polymarket-alpha-lab`（命令里写完整地址，不依赖本地 `origin` 指向哪里） |
| 交付分支 | `handoff/audit-2026-11-12` |
| 审核基线 | `e8c8a95cd9fea90db02518879e7d30931b5f6926` |
| 交付提交 | `8531ebcfb0e7c76b36ad93238a7a7282676beefc` |
| 交付目录 | `docs/handoffs/2026-11-12-audit/`，20 个文件，git 树对象 `f9f74f79056a7cf98980afff5961d44f469a67f2` |
| 清单 | 该目录下的 `MANIFEST.sha256`：2316 字节，19 行，SHA-256 `c720ad8c9f472f0ba023515badf18d4b0ea8abaf007d308ba2a013a10e3b19be` |

把下面的命令保存成仓库之外的一个脚本文件，在仓库检出的根目录用 `bash` 运行。它只读取，不改动
任何东西；任何一步不符都会以非零状态退出，这时停下来把输出报告给我，不要继续，也不要换别的
来源代替。校验读的是 git 对象而不是工作区文件，所以不受换行符转换的影响。命令是 bash 写法
（Linux，或 Windows 上的 Git Bash）。

```bash
set -euo pipefail
REPO=https://github.com/wmqfl861/polymarket-alpha-lab.git
DELIVERY=8531ebcfb0e7c76b36ad93238a7a7282676beefc
BASE=e8c8a95cd9fea90db02518879e7d30931b5f6926
DIR=docs/handoffs/2026-11-12-audit

# 1. a clean checkout, and the delivery commit is reachable from the retained branch
test -z "$(git status --porcelain)" || { echo "STOP: working tree not clean"; exit 1; }
git fetch "$REPO" handoff/audit-2026-11-12
git cat-file -e "$DELIVERY^{commit}"
git merge-base --is-ancestor "$BASE" "$DELIVERY"
git merge-base --is-ancestor "$DELIVERY" FETCH_HEAD

# 2. the delivery touches nothing outside the handoff directory
test -z "$(git diff --name-only "$BASE" "$DELIVERY" | grep -v "^$DIR/" || true)" \
  || { echo "STOP: delivery changes files outside $DIR"; exit 1; }
test "$(git diff --name-only "$DELIVERY" FETCH_HEAD)" = "$DIR/05-local-agent-prompt.md" \
  || { echo "STOP: unexpected changes after the delivery commit"; exit 1; }

# 3. pinned tree, file count and manifest
test "$(git rev-parse "$DELIVERY:$DIR")" = "f9f74f79056a7cf98980afff5961d44f469a67f2" \
  || { echo "STOP: directory tree mismatch"; exit 1; }
test "$(git ls-tree -r --name-only "$DELIVERY" -- "$DIR" | wc -l)" -eq 20 \
  || { echo "STOP: file count mismatch"; exit 1; }
test "$(git cat-file blob "$DELIVERY:$DIR/MANIFEST.sha256" | wc -c)" -eq 2316 \
  || { echo "STOP: manifest size mismatch"; exit 1; }
test "$(git cat-file blob "$DELIVERY:$DIR/MANIFEST.sha256" | sha256sum | cut -d' ' -f1)" \
  = "c720ad8c9f472f0ba023515badf18d4b0ea8abaf007d308ba2a013a10e3b19be" \
  || { echo "STOP: manifest hash mismatch"; exit 1; }

# 4. every file listed in the manifest matches its hash
git cat-file blob "$DELIVERY:$DIR/MANIFEST.sha256" | while read -r sum path; do
  actual=$(git cat-file blob "$DELIVERY:$path" | sha256sum | cut -d' ' -f1)
  if [ "$actual" != "$sum" ]; then echo "STOP: MISMATCH $path"; exit 1; fi
done
echo "handoff package verified: $DELIVERY"
```

预期的最后一行输出是 `handoff package verified: 8531ebcfb0e7c76b36ad93238a7a7282676beefc`。

### 4. 允许与禁止

**允许**

- 阅读仓库的任何文件；在开发环境里运行测试和 `scripts/verify_local.py`。
- 按 `03-fix-list.md` 修改和新增文件，范围限于各泳道的文件集合。
- 新增迁移文件（已有的不动；同时更新迁移清单和两处迁移计数测试；账本 v2 的迁移另需 OD-D）。
- 在运行服务器上做只读清点和只读查询。
- 节点通过全部门之后，按现行做法推送 `main`。

**禁止**

- 任何真实交易、账户认证、钱包、私钥、签名、下单相关的代码或操作。
- 读取、打印、移动或提交任何凭据；不要读 `~/pal-artifacts`。
- 修改冻结内容：四个闸门阈值、十变体集合、`selfcheck` 的 10 项检查、
  `tests/fixtures/papersim/` 下的夹具。
- 修改、删除或重放已有的迁移文件；删除迁移清单的条目；删除数据库的表。
- 对账本已有的行执行 `UPDATE` 或 `DELETE`。
- 在我对 OD-H 选 ① 之前替换账本数据库里的视图（FX-02 的替换段）。
- 在我对 OD-B 选 ① 之前删除或移动任何不可达代码。
- 在我答复 OD-E 并确认成稿之前修改 `AGENTS.md`。
- 在我对 OD-A 选 ② 之前修改 V1 的源码或启动任何真实模型调用。
- 在我确认之前做 FX-21（令牌的传递方式）。
- 在我批准 OD-G 之前启用新的晋级判定或暂停规则。
- 顺手修改三个守卫测试的白名单（`tests/test_phase1_live_surface_guard.py`、
  `tests/test_database_persistence_iron_rule.py`、`tests/test_supabase_durable_only_scope.py`）。
  确实需要改时，写进节点计划并经复审。
- 为了让改动通过而删除、跳过或放宽测试；为了与服务器脚本"对齐"而放宽库里的闸门。
- 强制推送；跳过独立只读复审；使用快速模式。
- 把服务器的公网地址写进任何新文件。

### 5. 环境

- 在你平时开发本项目的仓库检出里工作，平台按 `AGENTS.md` 的现行规定。
- Python 环境：`uv sync --locked --extra dev --extra postgres --python 3.12`
- 全量离线验证：`.venv/bin/python scripts/verify_local.py --full`（Windows 下解释器是
  `.venv\Scripts\python.exe`）。基线上 CI 的结果是 41,262 通过、121 跳过、0 失败（GitHub
  Actions 运行 `42966642867`）。动手之前先在你的检出上跑一次，把结果记下来作为起点；与基线
  不同就先弄清原因。
- 模拟盘自检：`.venv/bin/python -m polymarket_alpha_lab.papersim.cli selfcheck`，最后一行应为
  `selfcheck: PASS (10/10 checks)`。把完整输出存一份，之后每个节点都与它逐字节比较。
- 运行服务器上的 `~/paper-sim` 目录和 `paper_sim` 数据库，只按第 4 节允许的方式接触。

### 6. 执行步骤

**步骤 0：把交接包合入 `main`**

第 3 节的校验通过之后执行，同样保存成仓库之外的脚本文件，在仓库检出的根目录用 `bash` 运行。
如果交付提交已经在 `main` 里，它会直接退出，不做任何事。

```bash
set -euo pipefail
REPO=https://github.com/wmqfl861/polymarket-alpha-lab.git
DELIVERY=8531ebcfb0e7c76b36ad93238a7a7282676beefc
DIR=docs/handoffs/2026-11-12-audit

test -z "$(git status --porcelain)" || { echo "STOP: working tree not clean"; exit 1; }
git checkout main
git pull --ff-only "$REPO" main
if git merge-base --is-ancestor "$DELIVERY" HEAD; then
  echo "already merged: nothing to do"; exit 0
fi
PRE=$(git rev-parse HEAD)
git fetch "$REPO" handoff/audit-2026-11-12
git merge --no-edit FETCH_HEAD
test -z "$(git diff --name-only "$PRE" HEAD | grep -v "^$DIR/" || true)" \
  || { echo "STOP: merge changed files outside $DIR"; exit 1; }
git merge-base --is-ancestor "$DELIVERY" HEAD
echo "merged locally, not pushed: $(git rev-parse HEAD)"
```

交接包只新增一个目录，不应有冲突；有冲突就停下来报告，不要强行解决。脚本只在本地合并，不推送。
合并是一个节点，照常过门：全量离线验证、`git diff --check`、秘密扫描、独立只读复审（复审范围
包括这份提示词，以及交接包 `README.md` 里说明的"复审之后的修订"）。通过后推送到上面这个仓库的
`main`，另一个仓库按现行的同步做法处理，并记下两边 `main` 的提交号。交付分支上 CI 不会运行；
推送 `main` 之后，把那次离线验证工作流的运行编号和结果记下来。

**步骤 1：阅读**

按顺序读 `docs/handoffs/2026-11-12-audit/` 下的 `README.md`、`01-audit-report.md`、
`02-blueprint-v2.md`、`03-fix-list.md`、`04-development-plan.md`。行号对应审核基线；`main` 如果
已经前进，以符号名为准重新定位。

**步骤 2：九项只读核实**

逐项回答 `01-audit-report.md` 第 8 节的 V-1 至 V-9，每项写明结论、依据（文件和行号，或命令和
输出摘要）、核实时间。全部是只读操作。结果写进计划记录——默认是 `DELIVERY_PLAN.md` 的一个
新小节，由你这个协调者落笔，登记方式见蓝图 8.1。这个小节的第一条写明本轮工作的授权来源：
我把这份提示词交给你的那条消息，原话照录。

**步骤 3：一次性提交决定请求**

把 `02-blueprint-v2.md` 第 9 节的 OD-A 至 OD-H 整理成一份请求交给我，每项带上推荐、默认做法，
以及步骤 2 里与它有关的核实结果。只问一次。我没有答复的项按默认做法执行，并在状态板上标明
"按默认"。不要因为等答复而停工。

**步骤 4：M0 的五条泳道**

按 `04-development-plan.md` 第 4 节同时开 A、B、C、D、E 五条泳道，文件所有权照表执行，共享
文件走单写者。每个节点的流程照该文件第 3 节。注意三点：

- 11-24 之前给出 FX-04 的结论。没有接线证据，就把跨联赛胜负盘队列标为冻结，不恢复入场。
- FX-02 的只读段做完后，立即用 FX-01 的报告脚本对新导出的账本出一份净口径报告交给我。
  这份报告不需要等 OD-H。
- 泳道 D 的"出现 `SyntaxWarning` 即失败"，必须等泳道 A 修好
  `tests/test_papersim_gates.py:847` 并合并之后再合并。

**步骤 5：M0 出口检查**

逐条核对 `04-development-plan.md` 第 4.4 节的九个勾选项，给我一份 M0 总结（内容见第 9 节）。

**步骤 6：继续**

M0 出口通过后按计划进入 M1，再到 M2。M3 里不依赖决定的节点（FX-20、FX-22 的其余三项、
FX-24 中不涉及 `AGENTS.md` 的部分）可以从现在起用空闲产能做。依赖决定的节点等到相应的答复。

### 7. 验收标准

- 每个条目的验收标准在 `03-fix-list.md` 对应的小节里，逐条满足并留证。
- 里程碑的出口标准在 `04-development-plan.md` 第 4.4、5.2、6.3 节和第 7 节末尾。
- 每个节点：聚焦测试通过；全量离线验证通过；`git diff --check` 干净；编译检查通过；秘密扫描
  无命中；`selfcheck` 10/10 且原有输出逐字节不变；独立只读复审给出 `VERDICT: PASS`。
- 新增模块要么能从入口走到，要么在状态板登记为影子，并写明晋级条件和到期日。

### 8. 失败处理

- 第 3 节任何一条校验不符：停止，报告实际值，不要用别的来源替代。
- `git fetch` 因为认证方式失败：把 `REPO` 换成你访问这个仓库惯用的地址（例如 SSH 写法）再试；
  校验只认提交号和校验值，与传输方式无关。仍然取不到就报告。
- 工作区不干净：停下来报告，不要 stash，也不要丢弃已有的改动。
- `main` 已前进导致行号对不上：以符号名重新定位；定位不到就报告，不要猜。
- 测试失败：保留首次失败的完整输出；修复后重跑；首次失败和重跑分开记录。
- 复审不通过：按发现修改后重新送审，不要换一个复审者来"重试"同一份改动。
- 运行服务器不可达：把泳道 C 标为受阻并写明现象，其余泳道继续。
- 交接包里的陈述与你看到的仓库或服务器事实不符：以事实为准，把差异写进计划记录并在汇报里
  单列。不要默默照做，也不要默默改掉。
- 平台拒绝某次写入或推送：记录障碍，不要换接口或换编码绕过。

### 9. 需要返回的证据

每个节点一段话，格式固定：

> 本次节点和对应条目 → 固定提交号、测试结果（含首次失败与重跑）、复审结论 → 这个里程碑还差
> 什么 → 状态板有没有变 → 下一步是什么、是否在等我。

M0 结束时另给一份总结，包含：

1. 第 3 节校验脚本的输出，步骤 0 之后 `main` 的提交号，两个仓库 `main` 的提交号；
2. V-1 至 V-9 各自的结论；
3. OD-A 至 OD-H 各自的状态（已答复的写答复，未答复的写"按默认"）；
4. 账本净口径报告：各队列的入场数、结算数、毛回报率、净回报率，以及费率归类表；
5. 业绩视图的现状；如果 OD-H 选了 ①，再加修复前后的对比；
6. 真实数据库 CI 的运行编号和结果；
7. 跨联赛胜负盘队列的状态及依据；
8. 每个已完成节点的提交号和复审结论；
9. 没有执行或被挡住的事项，以及各自的原因。

任何汇报、日志或提交里都不要出现凭据、数据库密码或服务器的公网地址。
