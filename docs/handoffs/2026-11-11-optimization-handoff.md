# Handoff: 2026-11-11 审核后续优化（给本地 agent / ZCode 协调者）

本文件本身就是交付物，遵照 `AGENTS.md`"Current owner instruction: complete GitHub-first
handoffs"的六条要求撰写：目标、已完成且不要重做的工作、精确版本号、允许/禁止操作、
环境与校验、精确命令、验收标准、失败处理、需要回报的证据，全部写在本文件里，不依赖
"见上文"或聊天记录。

## 0. 这是什么、不是什么

这是一轮**只读静态审核**（Claude 云端会话，未克隆执行、未连接数据库、未登录服务器）的产出，
不是实现。所有需要动服务器/数据库/生产配置的步骤都明确标成"需要人工/本地 agent 执行并回报"，
不是审核本身已经做过的事。

## 1. 目标

按 `docs/reviews/review-2026-11-11.md`（commit `e2ded8f9`，建立在 `docs/reviews/review-2026-11-05.md`
之上）里 §9 的 Phase 0/1/2 路线，推进优化与修改；本文件把 Phase 0 的 7 项拆成可以直接逐条执行、
逐条回报的任务。

## 2. 已完成、不要重做的工作（避免重复劳动）

- `76934762`：交易费计入闸门——**已验证修复**，`gates.py:374` 的 `_apply_fee_and_haircut`
  被两个入口共用，不需要再动。
- `5bdae2e3`/WP-P4/WP-P5/WP-NBA 的模型验证纪律——**流程是对的**（影子→验证门→预登记标准→
  独立复审），不要因为本报告提到"代码质量差"就去改模型验证逻辑本身，那不是本次审核的发现目标。
- `importgraph.py`/`codequality.py` 的核心逻辑——**不需要重写**，只需要打下面 §3.6 这一个
  一行补丁。

## 3. 精确版本与允许/禁止操作

- 基准 commit：`e2ded8f9`（本次审核文档落地点），其父提交是本周工作的 HEAD `026f9585`。
- 仓库：`wmqfl861/polymarket-alpha-lab`，分支 `main`，直接 push（项目当前工作方式，不需要开 PR，
  除非你自己判断某一项改动风险大到想要独立复审先把关——那就按 Iron Rule 4 走独立只读复审子代理，
  跟平时一样）。
- **禁止**：任何实盘下单、私钥/账户凭证处理、绕过 `validate_local_postgres_dsn` 的数据库连接——
  这些是项目既有的 Phase 1 边界（`AGENTS.md` Iron Rule 1/3），本次审核不改变、也不建议改变它们。
- **禁止**：为了让某个 gate 通过而下调阈值（6c spread、5c/4c 边际门槛等）——`model-review-2026-11-07.md`
  已经明确裁定这些阈值维持冻结，本次审核同意这个裁定，不建议重新讨论。
- **允许**：按下面逐条任务修改 `AGENTS.md`、`.github/workflows/*.yml`、`cli.py`、`backup.py`、
  `src/polymarket_alpha_lab/cli.py` 里 token 传参方式；允许运行迁移、重算历史 PnL。

## 4. 环境与校验（下载/确认起点）

```bash
# 确认你本地/服务器的工作副本确实在正确的起点上
git -C <你的本地仓库路径> fetch origin main
git -C <你的本地仓库路径> log --oneline -3 origin/main
# 应该能看到 e2ded8f9 (docs: 2026-11-11 full review ...) 在历史里
git -C <你的本地仓库路径> show e2ded8f9 --stat
# 读完整审核报告（本地读，不要用 WebFetch 等工具去抓 claude.ai 链接，报告本身就在仓库里）
cat <你的本地仓库路径>/docs/reviews/review-2026-11-11.md
```

## 5. 逐条任务：精确命令 + 验收标准 + 失败处理

### 5.1 改写 Iron Rule 6（最高优先级，详见审核报告 §7/§9 Phase 0 第 1 条）

- **做什么**：在 `AGENTS.md` 的 "6. Sustained parallel development is a project iron rule." 条目后面，
  加一条平衡条款：当 `tools/analysis/importgraph.py` 报告的未接入模块行数 /已接入模块行数 的比例超过
  某个阈值（报告建议 5 倍；当前实测比例约 **14 倍**——2,310,547 / 164,284 ≈ 14.06，远超建议阈值，
  说明这条新规则一旦生效会立刻要求把相当一部分并行产能转向存量清理，这正是目的）时，新开并行任务
  至少应按比例分配给"接入或删除存量未接入模块"，而不是全部投向新功能。
- **这是文字/流程改动，不是代码改动**，不需要测试，但需要 owner 确认（这是 owner 自己写的项目规则，
  不是代码规范，建议先用 `AskUserQuestion` 或直接找 owner 确认措辞后再落笔，不要擅自替 owner 改规则）。
- **验收**：`git diff AGENTS.md` 里能看到新增条款；下一次 `importgraph.py` 跑出来的
  "未接入模块行数" 如果连续两周没有下降趋势，视为这条新规则没有被真正执行，需要升级给 owner。
- **回报**：commit message 里引用本文件路径 + "Iron Rule 6 amendment, per 2026-11-11 review §7"。

### 5.2 给 `native-postgres.yml` 加可靠触发器

- **做什么**：二选一（或都加）：
  ```yaml
  on:
    workflow_dispatch:
    schedule:
      - cron: '0 18 * * *'   # 每日 UTC 18:00，即台北 02:00
    push:
      branches: [main]
    pull_request:
      branches: [main]
      paths: [ ... 保留原有白名单 ... ]
  ```
- **验收**：`gh workflow run native-postgres.yml` 能手动触发成功；或等到下一个整点验证 `schedule`
  确实在 Actions 页面出现一次 `schedule` 事件的运行记录。
- **失败处理**：如果数据库相关测试在 CI runner 上因为没有真实 Postgres 实例而大批失败，这是预期的
  （需要先确认 workflow 里有没有起一个 Postgres service container），不要为了让它变绿就把断言改松；
  按 `workflow` 文件里原有的 `services:`/容器配置方式补起来，这部分请求独立复审子代理按 Iron Rule 4
  把关一次再合并。
- **回报**：commit message + 一次成功的 workflow run 链接。

### 5.3 GitHub 账号升级决策（不是代码任务，是一次性决策）

- **做什么**：这是需要 owner 决定的一次性事项，不是代码改动——`AskUserQuestion` 问 owner：
  "升级到 GitHub Pro（约 $4/月，开通后可对 private repo 设置 branch protection/rulesets）还是暂时
  接受拿不到平台级分支保护，退而求其次用 CI-must-be-green 的软约束？"
- **验收**：owner 给出明确答复；如果选择升级，升级后重跑
  `gh api repos/wmqfl861/polymarket-alpha-lab/branches/main/protection` 确认不再是 403，
  再配置：require status checks (`Offline verification`) + require review（如果这时候项目工作方式
  允许开 PR 的话）。

### 5.4 `llm_api_token` 改成带外文件注入

- **做什么**：参照 `AGENTS.md` 里 `PAPERSIM_PG_PASSWORD_FILE` 的既有模式，在 `cli.py:3098` 和
  `cli.py:4420` 两处 `--llm-api-token` 参数旁边新增 `--llm-api-token-file`（读文件内容做 token，
  文件路径本身可以出现在命令行，token 内容不出现），逐步把 `--llm-api-token` 标记为 deprecated
  但保留兼容（不要直接删除，避免破坏现有调用方）。
- **验收**：新增一个测试覆盖"同时传两者时该怎么处理/只传 file 版本时行为正确/token 不出现在
  `ps aux`可见的参数列表里"；现有 `tests/test_papersim_cli.py` 等相关测试保持通过。

### 5.5 确认并应用 `20261107000000_papersim_perf_view_fix.sql`，重算历史 ROI

- **做什么**（这一步必须有数据库访问权限的人/agent 执行，云端审核会话做不到）：
  1. 连接到实际跑纸面交易的那个 Postgres 实例，确认该 migration 是否已在 `schema_migrations`
     之类的记录里；
  2. 如果没有，按项目既有迁移流程执行它；
  3. 执行后，对**全部**已结算记录重新计算 PnL/ROI，产出一份新的、单一口径的结算汇总，替换掉
     目前分散在 `review-2026-11-05.md`、它的 archival commit message、`model-review-2026-11-07.md`
     三处互相不一致的 40/47/53/58 笔数字。
- **验收**：新汇总数字 + 对应的 `model_performance` 视图查询 SQL 一并记录进
  `DELIVERY_PLAN.md`（新增一节，按项目惯例标明来源 commit/migration）。
- **失败处理**：如果发现 migration 应用后数字跟之前任何一次报告的数字都对不上，**不要自行"修正"
  成看起来合理的数字**，如实记录差异并标注为待调查。

### 5.6 `backup.py` 加密

- **做什么**：`backup.py:177`/`:193` 的 `'encrypted': False` 改为实际加密（age 或 gpg，选项目
  工具链里已有的那个），密钥管理沿用 Postgres 密码那套"带外、不入库"的方式。
- **验收**：新增测试证明备份文件在磁盘上确实是密文（不是明文加个扩展名）；现有 backup 相关测试
  （11-07 报告提到的因端口占用失败的 4 个测试，先确认是否是环境问题还是真的坏了）一并清理。

### 5.7 `cli.py` 的 24 处重复 except 模式

- **做什么**：抽一个 `_run_subcommand(name: str, fn: Callable[[], int]) -> int` 包装，内部用
  `logging.exception()` 记录完整 traceback 后再打印一行给用户看的简短消息，替换 `cli.py` 里
  24 处 `except Exception as exc: print(f"... failed: {exc}", file=sys.stderr); return 1` 模式。
- **验收**：`grep -c` 确认该模式从 24 降到 0（或降到一个你能逐个说明理由的更小数字）；
  `tests/test_papersim_cli.py` 等现有 CLI 测试保持通过；新增至少一个测试断言失败路径确实有
  traceback 被记录下来（不只是打印一行文本）。
- **这一项风险低、范围明确，建议作为 Phase 0 最先落地的代码改动**（跟 Iron Rule 6 的文字改动
  可以并行推进，互不冲突）。

### 5.8 `codequality.py` 前缀 bug（可选，低优先级，但建议顺手修）

- **做什么**：`tools/analysis/codequality.py` 第 76 行附近 `path.relative_to(src.parent)` 改成
  `path.relative_to(src)`，使其模块命名跟 `importgraph.py` 的 `_used_modules` 对齐。
  本次审核报告 §3 的"已接入代码卫生更差"结论就是用这个修复验证出来的。
- **验收**：修复后重跑，`functions_used`/`hygiene_in_used_modules` 不再恒为 0。

## 6. Phase 1/2 的前置分类步骤（不要求本周完成，纳入待办）

- 在做任何批量删除之前，先把 `not_used_by_cli` 的 2,435 个模块分成"有 DELIVERY_PLAN 条目+测试+
  明确晋级/过期日期"（影子候选，保留）和"没有晋级路径记录"（孤儿，可删）两桶，具体规则见
  `review-2026-11-11.md` §10 Phase 1。
- 把 `~/paper-sim/` 下的调度脚本纳入版本控制（或至少建一个"服务器当前运行 commit SHA"状态文件），
  作为 Phase 2"G2 首次真实运行"的前置条件，见 `review-2026-11-11.md` §8/§9。

## 7. 需要回报的证据（每完成一项都要有）

- 对应的 commit SHA + 改动文件列表；
- 相关测试套件的运行结果（passed/skipped/failed 具体数字，不要只说"测试过了"）；
- 如果该项触发了独立复审子代理（Iron Rule 4 要求的那种），附 `VERDICT: PASS/FAIL` 那一行；
- §5.5/§5.2 这类依赖服务器或数据库状态的项，回报里必须包含你实际查询到的原始证据
  （迁移记录、workflow run 链接），不是"应该已经做了"这种推测性陈述。

---

读本文件 + `docs/reviews/review-2026-11-11.md` 两份就够了，不需要额外去 claude.ai 找链接或翻聊天记录。
