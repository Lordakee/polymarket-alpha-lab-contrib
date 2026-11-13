# 03 给本地代理的提示词

"提示词正文"一节可以整段复制给本地代理（项目的协调者）。它是自包含的：目标、不要重复的工作、
固定版本、允许与禁止、环境、步骤、验收、失败处理、要返回的证据都在里面。

固定值：

| 项目 | 值 |
| --- | --- |
| 仓库 | `https://github.com/wmqfl861/polymarket-alpha-lab` |
| 交付分支（保留，不删） | `handoff/m0-review-2026-11-13` |
| 被审核的提交（本分支的起点） | `b5ab6108d9e72ee37ce43f8247221f4f674d1224`（`main`，2026-11-12） |
| 交付提交（文档、证据、清单） | `99c12342e53c9411a5cc218acf538c46da8b8018` |
| 交付目录 | `docs/handoffs/2026-11-13-m0-review/`，在交付提交里共 13 个文件，目录的 git 树对象 `b7a097a03854be6afaaeecc9686394fd795fa252` |
| 清单文件 | `docs/handoffs/2026-11-13-m0-review/MANIFEST.sha256`，1526 字节，12 行，SHA-256 `f8c82afc632ece33088f72f8d2331be3c11187166f6258d3653a16b77d9577ee` |
| 固定网址（需要登录） | <https://github.com/wmqfl861/polymarket-alpha-lab/tree/99c12342e53c9411a5cc218acf538c46da8b8018/docs/handoffs/2026-11-13-m0-review> |

`MANIFEST.sha256` 逐行列出除它自己以外的 12 个文件的 SHA-256（包括
`MANIFEST.json`，后者另外记录了每个文件的字节数）。本文件在交付提交之后的下一个提交里，不在清单
的覆盖范围内。

---

## 提示词正文

你是 polymarket-alpha-lab 项目的协调者。2026-11-13 的独立审核对 M0 执行成果的结论是不通过
（`VERDICT: FAIL`）：代码和取证的质量得到认可，卡在四条流程问题上。请按仓库里的审核交接包完成
整改，然后交回复审。全程遵守仓库根目录 `AGENTS.md` 的现行规则；本提示词或交接包与 `AGENTS.md`
冲突时，以 `AGENTS.md` 为准，并把冲突报告给我。

### 1. 目标

1. 核对审核交接包的完整性，把它合入 `main`。
2. 把我 2026-11-13 的两条原话和八项决定的结果记进 `DELIVERY_PLAN.md`。
3. 完成整改节点 R-01 至 R-08；两条工作流（离线验证、真实数据库）在 Linux 上都跑绿，记下运行编号。
4. 重核 M0 出口（R-09），写整改交付书并推送（R-10），把终点提交号告诉我。

### 2. 已经完成、不要重复的工作

- 审核已经做完，结论和证据都在交接包里。不要重新审一遍；只在动手前复核你要改的那几处。
- M0 泳道 A、B、C 的代码和取证成果已被审核认可，不要返工。
- 八项决定（OD-A 至 OD-H）我已经答复，结果在审核报告开头的表里，不要再问我。以后提交给我的
  决定项，我没有另行答复的，按审计方的推荐执行。审计方对涉及真实资金、凭据、真实下单的事的推荐
  一律是"由我单独明确确认"，所以这类事仍然要等我明确答复。
- 审计方的输出形式由我来定：每一轮的审核文档都会发布到仓库的一个保留分支，并通过我给你一份提示词。
  你的交付书不需要规定审计方怎么输出。
- 2026-11-11 那份已作废的审核和交接仍然不要执行。

### 3. 固定版本与完整性校验

| 项目 | 值 |
| --- | --- |
| 仓库 | `https://github.com/wmqfl861/polymarket-alpha-lab`（命令里写完整地址，不依赖本地 `origin` 指向哪里） |
| 交付分支 | `handoff/m0-review-2026-11-13` |
| 被审核的提交 | `b5ab6108d9e72ee37ce43f8247221f4f674d1224` |
| 交付提交 | `99c12342e53c9411a5cc218acf538c46da8b8018` |
| 交付目录 | `docs/handoffs/2026-11-13-m0-review/`，13 个文件，git 树对象 `b7a097a03854be6afaaeecc9686394fd795fa252` |
| 清单 | 该目录下的 `MANIFEST.sha256`：1526 字节，12 行，SHA-256 `f8c82afc632ece33088f72f8d2331be3c11187166f6258d3653a16b77d9577ee` |

把下面的命令保存成仓库之外的一个脚本文件，在仓库检出的根目录用 `bash` 运行。它只读取，不改动
任何东西；任何一步不符都会以非零状态退出，这时停下来把输出报告给我，不要继续，也不要换别的
来源代替。校验读的是 git 对象而不是工作区文件，所以不受换行符转换的影响。命令是 bash 写法
（Linux，或 Windows 上的 Git Bash）。

```bash
set -euo pipefail
REPO=https://github.com/wmqfl861/polymarket-alpha-lab.git
DELIVERY=99c12342e53c9411a5cc218acf538c46da8b8018
BASE=b5ab6108d9e72ee37ce43f8247221f4f674d1224
DIR=docs/handoffs/2026-11-13-m0-review

# 1. a clean checkout, and the delivery commit is reachable from the retained branch
test -z "$(git status --porcelain)" || { echo "STOP: working tree not clean"; exit 1; }
git fetch "$REPO" handoff/m0-review-2026-11-13
git cat-file -e "$DELIVERY^{commit}"
git merge-base --is-ancestor "$BASE" "$DELIVERY"
git merge-base --is-ancestor "$DELIVERY" FETCH_HEAD

# 2. the delivery touches nothing outside the handoff directory
test -z "$(git diff --name-only "$BASE" "$DELIVERY" | grep -v "^$DIR/" || true)" \
  || { echo "STOP: delivery changes files outside $DIR"; exit 1; }
test "$(git diff --name-only "$DELIVERY" FETCH_HEAD)" = "$DIR/03-local-agent-prompt.md" \
  || { echo "STOP: unexpected changes after the delivery commit"; exit 1; }

# 3. pinned tree, file count and manifest
test "$(git rev-parse "$DELIVERY:$DIR")" = "b7a097a03854be6afaaeecc9686394fd795fa252" \
  || { echo "STOP: directory tree mismatch"; exit 1; }
test "$(git ls-tree -r --name-only "$DELIVERY" -- "$DIR" | wc -l)" -eq 13 \
  || { echo "STOP: file count mismatch"; exit 1; }
test "$(git cat-file blob "$DELIVERY:$DIR/MANIFEST.sha256" | wc -c)" -eq 1526 \
  || { echo "STOP: manifest size mismatch"; exit 1; }
test "$(git cat-file blob "$DELIVERY:$DIR/MANIFEST.sha256" | sha256sum | cut -d' ' -f1)" \
  = "f8c82afc632ece33088f72f8d2331be3c11187166f6258d3653a16b77d9577ee" \
  || { echo "STOP: manifest hash mismatch"; exit 1; }

# 4. every file listed in the manifest matches its hash
git cat-file blob "$DELIVERY:$DIR/MANIFEST.sha256" | while read -r sum path; do
  actual=$(git cat-file blob "$DELIVERY:$path" | sha256sum | cut -d' ' -f1)
  if [ "$actual" != "$sum" ]; then echo "STOP: MISMATCH $path"; exit 1; fi
done
echo "review package verified: $DELIVERY"
```

预期的最后一行输出是 `review package verified: 99c12342e53c9411a5cc218acf538c46da8b8018`。

### 4. 允许与禁止

**允许**

- 按 `02-remediation-guide.md` 修改它列出的文件，范围限于各节点的文件集合。
- 在 Linux 上运行测试；手动触发真实数据库工作流。
- 在运行服务器上做只读清点和只读查询（R-07）。
- 整改节点满足 `AGENTS.md` 推送规则列出的全部条件之后推送 `main`。
- 并行做 M1 各条目的计划和计划复审（只读）。

**禁止**

- 任何真实交易、账户认证、钱包、私钥、签名、下单相关的代码或操作。
- 读取、打印、移动或提交任何凭据。连库时让客户端通过 `PAPERSIM_PG_PASSWORD_FILE` 读密码文件可以；
  除此之外不读 `~/pal-artifacts` 下的其它文件，确有需要先写进节点计划并经复审。
- 对线上账本数据库执行任何写操作，包括重跑视图迁移（OD-H 的结果是不执行）。
- 修改冻结内容：四个闸门阈值、十变体集合、`selfcheck` 的 10 项检查、`tests/fixtures/papersim/`
  下的夹具。修改、删除或重放已有的迁移文件。
- 为了让 CI 变绿而跳过、删除或放宽测试，或者把失败的测试挪出矩阵。
- 两条工作流都绿之前，推送整改节点以外的任何新功能节点；增量复审通过之前，开始归档（FX-18）。
- 修改 V1 的源码或启动任何真实模型调用。V1 的原生测试可以按 R-02 至 R-04 修。
- 在我确认成稿之前修改 `AGENTS.md`。
- 修改 `docs/handoffs/2026-11-12-audit/` 和 `docs/handoffs/2026-11-13-m0-review/` 下的文件。
- 顺手修改三个守卫测试的白名单。
- 强制推送、改写历史、跳过独立只读复审、使用快速模式。
- 把服务器的公网地址写进任何新文件，包括写成正则、拆开写或者写进命令示例。

### 5. 环境

- 这一轮的测试结论以 Linux 为准。原生 PostgreSQL 的测试在 Linux 上跑（服务器或 CI）；本地
  Windows 的结果只作参考，不能代替。
- Python 环境：`uv sync --locked --extra dev --extra postgres --python 3.12`
- 全量离线验证：`.venv/bin/python scripts/verify_local.py --full`
- 原生分区在本机跑的环境变量和命令，以 `.github/workflows/native-postgres.yml` 里
  "Prove isolated native partition"和"Prove native version switch"两步为准。
- 手动触发真实数据库工作流：在 GitHub 的 Actions 页面对 `main` 运行 "Native project PostgreSQL"，
  或用你上一次触发运行 `43245420705` 时的同样做法。
- 模拟盘自检：`.venv/bin/python -m polymarket_alpha_lab.papersim.cli selfcheck`，最后一行应为
  `selfcheck: PASS (10/10 checks)`。

### 6. 执行步骤

**步骤 0：把审核交接包合入 `main`**

第 3 节的校验通过之后执行，同样保存成仓库之外的脚本文件，在仓库检出的根目录用 `bash` 运行。
如果交付提交已经在 `main` 里，它会直接退出，不做任何事。

```bash
set -euo pipefail
REPO=https://github.com/wmqfl861/polymarket-alpha-lab.git
DELIVERY=99c12342e53c9411a5cc218acf538c46da8b8018
DIR=docs/handoffs/2026-11-13-m0-review

test -z "$(git status --porcelain)" || { echo "STOP: working tree not clean"; exit 1; }
git checkout main
git pull --ff-only "$REPO" main
if git merge-base --is-ancestor "$DELIVERY" HEAD; then
  echo "already merged: nothing to do"; exit 0
fi
PRE=$(git rev-parse HEAD)
git fetch "$REPO" handoff/m0-review-2026-11-13
git merge --no-ff --no-commit FETCH_HEAD
if [ -n "$(git diff --cached --name-only "$PRE" | grep -v "^$DIR/" || true)" ]; then
  git merge --abort
  echo "STOP: merge would change files outside $DIR; aborted, nothing committed"; exit 1
fi
git commit --no-edit
git merge-base --is-ancestor "$DELIVERY" HEAD
echo "merged locally, not pushed: $(git rev-parse HEAD)"
```

交接包只新增一个目录，不应有冲突；有冲突就停下来报告，不要强行解决。脚本只在本地合并，不推送；
它总是生成一个合并提交（`--no-ff`），这个合并提交就是本节点的提交。如果合并会改到交付目录之外的
文件，它会中止合并、什么都不提交，这时同样停下来报告。合并是一个节点：做 `git diff --check`、
秘密扫描和独立只读复审（复审范围包括这份提示词）。

**先不要单独推送这个合并。** `main` 的离线验证现在是红的（P1-1），再推一个红的顶端没有意义。在
本地合并的基础上接着做 R-01（它只改一个测试文件），两个节点各自过完复审之后一起推送，这样推上去
的 `main` 顶端离线验证是绿的。记下这次推送的运行编号和结论。

**步骤 1：阅读**

按顺序读 `docs/handoffs/2026-11-13-m0-review/` 下的 `README.md`、`01-review-report.md`、
`02-remediation-guide.md`。行号对应被审核的提交；对不上就以符号名为准。

**步骤 2：记录我的决定**

把审核报告"Owner 的决定"一节里我的两条原话和八项决定的表，原样记进 `DELIVERY_PLAN.md` §77.3，
状态板同步更新（属于 R-05，可以最先做）。OD-H 的结果是不执行，不要因为"按推荐"去重跑视图迁移。

**步骤 3：并行开整改泳道**

按 `02-remediation-guide.md` 第 1 节的表同时开 R-01 至 R-07。每个节点：写计划（改测试的要写明
"原来证明什么、改完证明什么"）、实现、在 Linux 上验证、一个聚焦提交、独立只读复审、推送、记下
被触发的工作流的运行编号和结论。R-01 已在步骤 0 里随合并一起推送。R-02、R-03、R-04 的复审范围要
包括 `a93f5fab` 和 `15c35a62` 的全部改动；R-05 的复审范围要包括 `b5ab6108`（R-08）。

**步骤 4：M0 出口（R-09）**

R-01 到 R-06 都合并之后，在同一个提交上：离线验证为绿；手动触发真实数据库工作流为绿（四个 Linux
分区，加 storage 分区里的版本切换一步）。两个运行编号记进 §77。然后逐条重核开发计划 4.4 的九个
勾选项。

**步骤 5：交回复审（R-10）**

写 `docs/handoffs/2026-11-13-m0-remediation.md` 并推送，内容照整改指引 R-10 的六项。然后给我一条
简短的消息：终点提交号、这个文件的路径、两条工作流的运行编号。

**步骤 6：之后**

交回之后不必等复审结论：只要两条工作流都是绿的，就可以按开发计划开始 M1 的实现节点（OD-D、OD-G
已经批准）。FX-18 的归档等增量复审通过之后再开始。11-24 恢复跨联赛胜负盘时，照 OD-F 的两个附加
条件办。

### 7. 验收标准

- 每个整改节点的验收标准在 `02-remediation-guide.md` 对应的小节里，逐条满足并留证。
- 两条工作流在同一个终点提交上都为绿，运行编号已记录。
- 没有任何测试被跳过、删除、放宽或挪出矩阵；被改的测试都写明了改动前后各证明什么。
- 状态板能回答"几条线、各到哪、等谁、CI 是不是绿的"；八项决定和我的两条原话已入档。
- 在终点提交上重跑 `evidence/` 里的两个证据脚本（用法写在各自开头）。`scan_mirror_tree.py` 的输出里
  `size mismatch=0`，命中列表里不再有交付书那一行。`address_occurrence_diff.py`（基线 `e8c8a95`）的
  输出里，以 `new:` 开头的行只剩镜像里的第三方测试夹具 `tools/tests/test_understat_refresh.py`。
- 最终是否通过由审计方的增量复审给出。

### 8. 失败处理

- 第 3 节任何一条校验不符：停止，报告实际值，不要用别的来源替代。
- `git fetch` 因为认证方式失败：把 `REPO` 换成你访问这个仓库惯用的地址（例如 SSH 写法）再试；
  校验只认提交号和校验值，与传输方式无关。
- 工作区不干净：不要 stash，也不要丢弃已有的改动。先把手头的改动按正常流程提交完，或者换到一个
  干净的克隆里执行；做不到就停下来报告。
- 实测与整改指引的判断不符（例如端口绑定失败的原因不是 TIME_WAIT）：以事实为准，把现象写清楚，
  在节点计划里提出改法并经复审，交回时单列。
- 修好一处之后 CI 又暴露新的失败：先分类——过期的常量、平台差异，还是真缺陷。前两类照同样的
  纪律修；真缺陷就停下来报告我，不要改测试去迁就。
- 没有可用的 Linux 环境：用 CI 的手动触发来验证，不要用 Windows 的结果代替。
- 复审不通过：按发现修改后重新送审，不要换一个复审者来"重试"同一份改动。
- 交接包里的陈述与你看到的事实不符：以事实为准，写进计划记录并在交回时单列。
- 平台拒绝某次写入或推送：记录障碍，不要换接口或换编码绕过。

### 9. 需要返回的证据

1. `docs/handoffs/2026-11-13-m0-remediation.md`（已推送到 `main`），含：固定版本；逐条处置表
   （发现编号、做了什么、提交号、证据）；两条工作流的运行编号和结论，包括过程中失败过的；每个节点
   复审的结论和发现摘要；"需本地 agent 复核"七项各自的结果；偏差和未完成事项。
2. 给我的一条简短消息：终点提交号、上面这个文件的路径、两条工作流的运行编号。

任何汇报、日志或提交里都不要出现凭据、数据库密码或服务器的公网地址。
