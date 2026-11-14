# Distribution signing-key retry Implementation Plan

> **For agentic workers:** 后续执行仅用 ZCode-native 子代理；可按 `superpowers:subagent-driven-development` 分配任务，但本文的文件所有权、只读审核和当前授权边界优先。本文是计划产物，不是实施或审核结论。

**Goal:** 在 C3 上给 Linux distribution 的官方 PostgreSQL 签名 key 下载复用已交付的有限重试参数，并用现有测试覆盖两个实际 workflow 片段。

**Architecture:** 只改变 distribution 的一条 curl 命令；参数化原下载片段提取函数和四个现有测试函数，保留其他断言与 fakecurl 实现。在现有 `DELIVERY_PLAN.md` 追加一段 WP-06／FX-07 关联维护记录，不建立新工作包、验证框架或报告层。

**Tech Stack:** Linux、Git、Bash、curl、GitHub Actions、Python 3.12、pytest、uv 锁定环境；实际 distribution CI 使用工作流自有的临时 PG18 前缀和私有测试集群。

**Spec:** 本次用户任务；C3 的 `AGENTS.md`、`DELIVERY_PLAN.md` §4／§77.3–77.8、`docs/handoffs/2026-11-13-m0-review/02-remediation-guide.md` §0／R-03／R-09，以及 `docs/handoffs/2026-11-12-audit/04-development-plan.md` §3。固定 source：`6add9b041754600109e17e6aa05b0cb99aaface6`。

## Global Constraints

- **当前只写此一个外部计划**：`D:\Projects\pal-remediation-plans-20261113\distribution-retry-final-plan-20261114.md`。创建前已确认不存在；没有实施、运行测试、连数据库、触发 CI、commit 或 push。本次用户指定的外部计划交付覆盖技能默认保存位置及当前阶段 GitHub-first 发布动作；不声称已经发布。
- 全部后续操作仍经 native 子代理执行，不启动外部 Codex／Claude／OpenCode，不更改任何模型配置、规则、AGENTS、权限或安全策略，不启用 fast mode。CodeGraph 按现行 owner override **N/A**，不初始化、不要求同步、不声称执行过。
- 保持 paper-only／report-only／readonly；不读取凭据文件、不启用真实提供商、不使用业务数据库、不重放迁移。SSH 仅通过 `remote.srv` 在内存解析既有目标，禁止把地址或凭据写进命令、计划、日志和报告。
- 独立计划审查及 final code review 必须分别使用 fresh、只读、未参与该改动规划／实施／测试的 native reviewer；缺 reviewer 即门禁阻塞。作者单独自审不能代替独立审核；不为 reviewer 设固定完成时限。
- 固定三文件所有权。动态发现并发容量，有独立工作即可并行，不设永久并发上限；本节点不运行资源争用实验。完整测试与 R03 的敏感复现若共用主机，由协调者安排不相互干扰的运行窗口，不取消另一工作者或修改其资源设置。
- 不新建 `tests/test_native_distribution_workflow.py`，不改 native-postgres workflow，不改触发器／矩阵／测试选择器／超时／依赖，不放宽断言，不添加 skip、`continue-on-error`、缓存 key、镜像 URL、TLS 或 APT 签名绕过。

## Review Focus

1. **提取错 job 或测试只覆盖 PG**：两个明确的 `(workflow, job_id)` 参数，四个测试全部参数化；distribution 缺重试时必须真实红。
2. **丢失 curl 参数、错误输出或签名顺序**：原静态 argv 和后续三行顺序逐项断言保留；shell 返回码测试覆盖 0／56／22／60。
3. **把 fake 当真实网络证明**：原 fake 用例只证明 argv 驱动的模拟尝试、shell 接线和退出码；实际 curl／APT／PG 依靠一次同 SHA 的 distribution CI。
4. **把 180 秒当总墙钟硬上限**：`--retry-max-time 180` 限制重试启动窗口；每次传输另有 `--max-time 60`，并受原 job 40 分钟约束。fake 不执行真实时钟、DNS、TLS、退避或 libcurl。
5. **把错误 SHA／跳过作业／旧绿灯当验收**：固定 retained ref→完整 C→实际 run/attempt→linux-kit 必需步骤；退休 Windows 的设计性 skipped 单列，R03／R09 未完成仍保留。

---

## 1. 本次实际读取的事实与基线

本地源码取自 `D:\Projects\polymarket-alpha-lab` 的 **`git show C3:path` 对象**，没有把旧 main 当 C3。本地 HEAD 为 `37b288956187de404ee0047bc0a5beeccbe9dbf6`；已有 `.scratch/` 不属于本任务，未改动。C3 tree 为 `22d2a7b79d4ae1d44c41abb5fccbd23afae53fe9`。

另通过既有 SSH 包装器只读核对 `/home/ubuntu/pal-m0-startup-20261113-yx2fyoje/checkout`：HEAD=C3、tree 同上、分支 `remed/integration`、当次 status clean；下表四个 workflow／测试／交付计划文件的工作区字节均等于 C3。该 checkout **没有 `.venv/bin/python`**；这不证明没有其它外部环境，也不授权复用 R03 环境。本次没有安装环境或运行源码。

| C3 文件 | bytes | SHA256 |
| --- | ---: | --- |
| `.github/workflows/native-distribution.yml` | 12143 | `5f18a8856b02e476d1c4f35e8b3086778dc9b3937d0d01287fd9daa1be98712d` |
| `.github/workflows/native-postgres.yml` | 26535 | `c81863a7697b3836c71f4edffac732b29cb5c8ecdbb361bec8c2192122d53a73` |
| `tests/test_native_postgres_workflow.py` | 29091 | `37820d421fbb2f587d81ce5c6dcc017a83809394d24b79b89a0ac1ca200eff64` |
| `DELIVERY_PLAN.md` | 307586 | `28e01bdf651ca4cbb995b535ca67bfd6828dbe8f585670edf94d57cfdef1e9e9` |

已全文读取两个 workflow 和现有测试文件；定位结果如下，行号均属 C3。

- distribution `:2–78` 只有无 inputs 的 `workflow_dispatch` 和 PR→main 的路径过滤，**没有 push/schedule**；`:78` 包含 workflow 自身路径。`:91–136` 的 Windows job 已退休；活跃 job 是 `linux-kit`，Ubuntu 24.04、40 分钟、uv 0.10.0、Python 3.12。
- distribution `:161–183` 的完整 PG18 装配步骤已有 `set -euo pipefail`。`:168` 是单独的 `sudo curl --fail --silent --show-error -o … https://www.postgresql.org/media/keys/ACCC4CF8.asc`，无 retry；随后按顺序写带 `signed-by` 的源、`apt-get update -qq`、`apt-get install -y -qq postgresql-18`，再复制 portable prefix。没有额外 gpg 命令；APT 仍使用原签名验证。
- native-postgres `:423–448` 使用同一步骤名、官方 URL、输出路径和 signed-by；`:430–433` **已有本计划目标 curl 参数**。既有提交 `213e87fcc2d730a78aa03c28b5b1a51a17c5b9f5` 实现该修复，`a9decad6df26d9d020e6e1dbd0db4b3910c39684` 补 fakecurl 测试，均已在 C3 中；不重做、不再改该 workflow。
- `tests/test_native_postgres_workflow.py:250–258` 的 `linux_key_download_script()` 从真正的 job/step/run body 提取到 `\nPREFIX=` 前，包含下载与 APT 顺序；`:270` 静态测试、`:288` shell 返回码测试、`:428` 瞬时 56 比较、`:454` 持续错误测试可直接复用。独立 distribution 测试文件在 C3 中不存在。
- distribution `:184–214` 已启用 `POLYMARKET_ALPHA_LAB_RUN_NATIVE_DISTRIBUTION=1`，执行原分发测试清单、保留 pipefail/PIPESTATUS、校验 tracked source 不变并上传 proof/kit。这个清单**不包含** `test_native_postgres_workflow.py`；参数化测试由本节点 Linux focused/full 覆盖，不假称实际 distribution CI 会运行它。
- `scripts/verify_local.py:51–63` 会去掉 `POLYMARKET_ALPHA_LAB_*` 和部分 Python/pytest 环境，**不会清掉全部 PAPERSIM/PG 开关**；`:176–193` 执行 compileall 与全量 pytest。外层环境隔离不可省。
- 当前计划中的关联是 **WP-06 Linux distribution 维护，关联 FX-07 的 CI 基础设施缺口**，不把 FX-07 原始 native-postgres 范围改写成新承诺。`DELIVERY_PLAN.md:3780–3782` 明确 R09 需最终同 SHA 的 Offline + Native 四 Linux 分区、storage version-switch 和聚合，以及其余出口；distribution 绿灯不关闭 R09，亦不证明 R03 storage 根因。

此前 Codex-C 服务器 read-only sandbox 失败、未实际读源码，其 FAIL 仅作漏项提醒。本文事实来自上述本次读取，不引用它作为源码核验或审核通过证据。

## 2. 文件所有权与工作隔离

| 角色 | 独占写范围 | 其它权限／交接 |
| --- | --- | --- |
| 当前计划作者 | 本外部计划一个新文件 | 源码只读；不承担独立 review |
| 后续 implementation worker | `.github/workflows/native-distribution.yml`、`tests/test_native_postgres_workflow.py` | 所有修改在独立 Linux worktree；不能修改 native-postgres 或 R03 文件 |
| DELIVERY_PLAN 单写者（协调者分配的 native 文档 worker） | `DELIVERY_PLAN.md` 的一个追加段 | 先从 R05／其它文档 writer 收回该文件写权；不能并写，最终与实现同一聚焦提交 |
| R03/rootcause worker | 本表三文件均**禁止修改** | 保持其既有授权文件；不借此节点作端口、资源争用或版本切换实验 |
| 测试 worker | 不改 tracked 文件；仅本节点独占环境、临时目录和脱敏证据 | 源码冻结后执行最终测试；不复用 R03 的 venv/temp/PG |
| plan reviewer／fresh final code reviewer | 所有对象只读，不创建／修改／删除文件 | 各自独立，输出 findings 和明确 `VERDICT: PASS` 或 `VERDICT: FAIL` |

## 3. 待执行准备与最小变更

以下所有 checkbox 和命令均是**后续步骤，本次未执行**。

- [ ] 独立计划 reviewer 读取本计划的确切 SHA256、C3 对象和现行 owner 约束；得到 PASS 且没有未决阻断才进入实施。作者不自批。
- [ ] 协调者分配上述文件写权。在 Linux 建独立工作树；保留原 integration checkout、R03 及其现有改动。路径或分支已存在即停并读其状态，不覆盖、不 reset。

```bash
PAL_SOURCE=/home/ubuntu/pal-m0-startup-20261113-yx2fyoje/checkout
PAL_BASE=6add9b041754600109e17e6aa05b0cb99aaface6
PAL_WT=/home/ubuntu/pal-m0-startup-20261113-yx2fyoje/worktrees/distribution-key-retry-20261114
PAL_BRANCH=remed/distribution-key-retry-20261114
set -euo pipefail
test "$(git -C "$PAL_SOURCE" rev-parse "$PAL_BASE^{tree}")" = 22d2a7b79d4ae1d44c41abb5fccbd23afae53fe9
test ! -e "$PAL_WT"
git -C "$PAL_SOURCE" worktree add -b "$PAL_BRANCH" "$PAL_WT" "$PAL_BASE"
test "$(git -C "$PAL_WT" rev-parse HEAD)" = "$PAL_BASE"
test -z "$(git -C "$PAL_WT" status --porcelain)"
UV_PROJECT_ENVIRONMENT="$PAL_WT/.venv" UV_PYTHON_DOWNLOADS=never \
  uv sync --locked --offline --extra dev --extra postgres --python 3.12 --project "$PAL_WT"
```

使用已有暖缓存和该工作树自己的 editable 环境；缺解释器／依赖缓存即记录准备阻塞，不借用共享环境、不更新 lock、不擅自扩大下载范围。若协调者要求从不同于 C3 的基线集成，先交回差异及所有权，不能把本计划偷偷换基线。

### 3.1 测试先行：只参数化既有下载测试

- [ ] 保留 `WORKFLOW` 仍指 native-postgres，以免其它矩阵、触发、聚合测试被误切换。新增一个简单参数元组常量，不增加 fixture/parser/helper/framework。

```python
KEY_DOWNLOAD_WORKFLOWS = (
    (WORKFLOW, 'linux-native-part'),
    (ROOT / '.github/workflows/native-distribution.yml', 'linux-kit'),
)
```

- [ ] 将现有签名改为 `linux_key_download_script(workflow, job_id)`，只把首行改为 `worker = jobs(workflow.read_text())[job_id]`；后面的 step 名、body 去缩进、`\nPREFIX=` 分界及 `assert separator` 原样保留，不复制一份下载段到测试里。
- [ ] 对以下**四个函数全部**加 `@pytest.mark.parametrize('workflow,job_id', KEY_DOWNLOAD_WORKFLOWS, ids=('postgres', 'distribution'))`，签名接收 `workflow, job_id`；各处实际片段调用改为 `linux_key_download_script(workflow, job_id)`。原 `curl_exit` 参数化与其它参数保留。

| 测试函数 | 每个 workflow 的用例及必须保留的断言 |
| --- | --- |
| `test_linux_signing_key_download_is_bounded_and_preserves_trust_order` | 1；完整 argv 等于 `['sudo','curl',*KEY_DOWNLOAD_ARGS]`，首两行和后续三行精确相等 |
| `test_linux_signing_key_download_shell_preserves_curl_result` | 4：0／56／22／60；精确 argv、返回码、诊断输出；非零时无 APT、注册或继续哨兵，成功才继续 |
| `test_linux_signing_key_download_recovers_transient_56_the_original_command_could_not` | 1；fake 下新命令 56→0、尝试 `['1','2']`，旧命令返回 56、仅 `['1']`；两侧 argv 和 stdout/stderr 断言不动 |
| `test_linux_signing_key_download_persistent_errors_exhaust_bounded_retries_and_fail_closed` | 3：56／22／60；fake 尝试 `['1','2','3','4']`，终态非零、保留诊断且不运行 APT／哨兵 |

`KEY_DOWNLOAD_ARGS`、`ORIGINAL_KEY_DOWNLOAD_COMMAND`、`write_fake_curl_and_sudo()`、`run_download_segment()` 保持原样；`jobs()` 与测试文件其余契约不动。原 fake 的 PATH 只含替身、环境不继承、实际 key 路径不写入，继续保持。

- [ ] 在 distribution 命令尚未修改时运行红灯命令（第 4 节净化环境下）。预期两个 workflow 各 9 项：PG 9 项仍过，distribution 9 项因 argv／恢复／尝试计数不符而失败。收集的 test id 必须同时有 `postgres` 与 `distribution`；编译／collection／环境错误不能当目标红灯。

```bash
"$PAL_WT/.venv/bin/python" -m pytest -q -ra tests/test_native_postgres_workflow.py -k signing_key_download
```

此处 `-k` 只用于红灯定位，不用于最终验收删减测试。不重复已完成 PG 修复或制造真实网络故障。

### 3.2 distribution 一条命令

- [ ] 只将 C3 distribution `:168` 改为以下命令，可按 PG 既有形态四行排版；前后上下文不动。

```bash
sudo curl --fail --show-error --no-progress-meter \
  --retry 3 --retry-all-errors --connect-timeout 15 --max-time 60 --retry-max-time 180 \
  -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
  https://www.postgresql.org/media/keys/ACCC4CF8.asc
```

保留 `set -euo pipefail`、install 目录、官方 URL、原 `-o` 路径、APT `signed-by`、源登记→update→install 顺序、prefix 装配及后续测试管道。去掉 `--silent` 改用 `--no-progress-meter`，保留首次错误与重试诊断；不接新管道、不吞 stderr、不 `|| true`。curl 最终非零仍立即阻断 APT；不以失败残片／旧缓存放行。

`--retry 3` 允许首次加最多三次重试；实际可能因时间预算更早停止。`--retry-all-errors` 会扩大可重试错误类别，不仅是 56；TLS 验证没有关闭，持续 60 仍失败。180 秒不是整个 curl、更不是整个装配步骤的硬墙钟上限。现有 fake 没有真实 libcurl、退避和时限实现，不据四次 fake 尝试承诺实际 curl 一定四次。

- [ ] 运行整个 `tests/test_native_postgres_workflow.py`，18 项下载用例和其它既有契约均须通过；不只重跑先前失败项。

**原来证明什么／改后证明什么：** 原测试对 native-postgres 的实际片段证明 argv、fail-closed shell 接线、模拟重试结果及不变的矩阵合同，对 distribution 无覆盖。改后同一断言集分别约束两个真实片段，PG 证明不削弱，新增 distribution 适用性；红绿只证明测试能发现接线缺口，不证明真实网络已恢复或 libcurl 的时序实现正确。

### 3.3 DELIVERY_PLAN 最小追加

- [ ] 单写者在 §77 末尾追加一个带日期的短段，标题使用“WP-06／FX-07 关联维护：distribution 官方签名 key 下载”，不用新的 WP／FX 编号，不重写历史状态板或 R03 根因结论。
- [ ] 内容限于：C3 完整 source、已交付 PG 重试两个提交不重复；此节点三个文件的精确范围；已实际发生的红绿结果及证据身份；未发生的 final full／独立复审／真实 CI 明写待证据；180 秒和 fake 的证明边界；R03 根因、R09 双绿及九项出口仍由原任务收尾，WP-06/G6、FX-07 总验收、V1 状态不据此转 DONE。
- [ ] 在最终验证前冻结三文件字节。不要预写本提交未来 SHA、CI run 或 PASS。固定实现 C 的后发生 review/CI 回执由协调者登记并在既有 Q／R10 机制固化，避免 amend 追逐自引用；本节点不新建交付框架或手册。若最终需要改这段文字，按新 tree 重新做相关最终门禁。

## 4. 独立自审、Linux 最终门禁与聚焦提交

- [ ] 作者对冻结后的三文件完整 diff **单独自审**，记录为 self-review：检查非下载区字节不变、四个函数均参数化、所有旧断言保留、无新增 helper/依赖、文档无虚构结果与敏感数据。此自审与下一步测试是独立列出的 pass，不称独立复审。
- [ ] 每个验证进程都在 `$PAL_WT` 工作目录及自己的 `.venv` 中运行。沿用 R06 §5 已有净化/脱敏执行方式，传入本节点的 root/python/evidence；不执行含 R06 修改逻辑的旧 runner、不改 verifier。外层按变量名清除 `POLYMARKET_ALPHA_LAB_*`、`PAPERSIM_*`、`PG*`、`WP_P4_READONLY_PG`、`DATABASE_URL`、`PYTEST_ADDOPTS`、`PYTEST_PLUGINS`、`PYTHONPATH`、`PYTHONHOME`，不读取／打印值；设置 smoke=0、plugin autoload=1（禁用）、UTF-8。每次 full 的 `TMPDIR`、`PYTEST_DEBUG_TEMPROOT` 是新建、独占、仓库外目录；不用会被 verifier 清除的 `PYTEST_ADDOPTS` 偷传 basetemp。设置值为：

```text
POLYMARKET_ALPHA_LAB_RUN_SUPABASE_SMOKE=0
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
PYTHONUTF8=1
```

- [ ] 在上述净化捕获环境执行以下真实入口，逐项保留 exit、UTC、完整脱敏输出、实际统计、skip 原因、文件 hash／tree。命令之间遇非零停止发布链，不靠覆盖日志、忽略错误或更改断言继续。

```bash
"$PAL_WT/.venv/bin/python" -m pytest -q -ra tests/test_native_postgres_workflow.py
"$PAL_WT/.venv/bin/python" scripts/verify_local.py --full
"$PAL_WT/.venv/bin/python" -m compileall -q src tests scripts
"$PAL_WT/.venv/bin/python" -m polymarket_alpha_lab.papersim.cli selfcheck
git -C "$PAL_WT" diff --check
```

focused 必须覆盖两个 workflow 全部参数；full 必须实际到达 `PASS: full pytest`、`PASS: full local verification` 且 exit=0（包括 editable/CLI/compile）；compile exit=0，diffcheck 无输出。显式 compile 是既有节点编译门，不用它替代 full。selfcheck 保持 194 exports、10/10、stderr 空、exit=0；既有原始 stdout 基线为 1623 bytes，SHA256 `791f9f95d52abfa442c51fdf701ce5c2dd04e51d7cdce2d904f73ee4ac02dd54`，按未改写 bytes 比较；不修改 selfcheck。full 是离线验证，不能冒充 PG 验收。

- [ ] **既有 secret scan**：复用 C3 `tests/test_phase1_docs_no_secret_tokens.py` 的 `SECRET_PATTERNS`，沿 R06 `06_verify_static.py:91–100` 的方式在内存提取 pattern，对 C3→最终三文件的所有新增行扫描，不新建扫描器/规则/allowlist，不执行那份含其它任务操作的脚本。只返回规则名、文件／行位置、计数和状态，不打印匹配值；额外检查新增内容无公网地址，不复制历史地址。原样保留 full 内已有文档 secret guard。这个新增行扫描不是全历史无秘密证明；任何新命中／读取错误均阻塞。审核者检查范围为全部三个 tracked diff，不能把仅旧 24 个文档的 guard 冒称这次改动已扫描。
- [ ] 对 C3 的 `git diff --name-only` 必须**恰为**上述三文件；`native-postgres.yml`、AGENTS、源代码、迁移、lock、R03 测试、冻结交接包无改动。按实际冻结文件 bytes/hash 与测试结果绑定；没有未决 release-blocking finding 后只 stage 三文件并作一个聚焦提交。

```bash
git -C "$PAL_WT" add -- .github/workflows/native-distribution.yml tests/test_native_postgres_workflow.py DELIVERY_PLAN.md
git -C "$PAL_WT" diff --cached --check
git -C "$PAL_WT" commit -m "fix(ci): bound distribution signing-key retries (WP-06/FX-07)"
PAL_C=$(git -C "$PAL_WT" rev-parse HEAD)
PAL_TREE=$(git -C "$PAL_WT" rev-parse HEAD^{tree})
test "$(git -C "$PAL_WT" rev-parse HEAD^)" = "$PAL_BASE"
test -z "$(git -C "$PAL_WT" status --porcelain)"
git -C "$PAL_WT" diff --check "$PAL_BASE" "$PAL_C"
```

核对 C 的三文件 blob 与刚完成最终门禁的字节完全相同，且全树没有额外变动；否则旧测试不得标为 C 通过。相关门禁需覆盖最终 tree，不能借 C3 或其它节点结果。

- [ ] **fresh final code review**：在 C 固定且 clean 后，新派未参与计划／实施／测试的只读 reviewer，交给它 C3→C 全 diff、本计划 hash、self-review、红绿、focused/full/compile/diffcheck/secret/selfcheck 证据和未执行项。reviewer 不写文件、不跑新的 DB 或 CI，输出 `VERDICT: PASS` 且无未决发布阻断才可发布。有发现则先修复、更新证据并针对新最终 revision 再 review；不改已发布历史，不把作者自审借名作独立审核。

## 5. retained 分支发布与一次实际 distribution CI

本节**仅后续实施门禁全部通过后**由获配的 native 发布子代理执行；用户已有 push 授权，不重复索要。当前计划阶段不执行。正本固定 `wmqfl861/polymarket-alpha-lab`；retained 分支选 `remed/distribution-key-retry-20261114`，不是 main，也不使用会自动触发 Offline 的 `dev/**` 命名。发布前确认远端该 ref 不存在；若已存在，先读取其 SHA/所有者并停，不能覆盖未知工作或 force-push。

- [ ] 在既有认证会话中发布已审 C，不读取 token，不改认证；记录完整 commit/tree，随后回读远端 ref。

```bash
git -C "$PAL_WT" ls-remote --heads https://github.com/wmqfl861/polymarket-alpha-lab.git "refs/heads/$PAL_BRANCH"
# 上行必须成功且零条；非零错误不是“分支不存在”。
git -C "$PAL_WT" push https://github.com/wmqfl861/polymarket-alpha-lab.git "HEAD:refs/heads/$PAL_BRANCH"
test "$(gh api "repos/wmqfl861/polymarket-alpha-lab/git/ref/heads/$PAL_BRANCH" --jq .object.sha)" = "$PAL_C"
test "$(gh api "repos/wmqfl861/polymarket-alpha-lab/git/commits/$PAL_C" --jq .tree.sha)" = "$PAL_TREE"
```

逐个回读 C 的三个文件：`gh api -H 'Accept: application/vnd.github.raw+json' "repos/wmqfl861/polymarket-alpha-lab/contents/<path>?ref=$PAL_C"`，与 `git -C "$PAL_WT" show "$PAL_C:<path>"` 的原始 bytes/SHA256 比较。用现有脱敏执行器在内存做 byte/hash 检查；不得执行下载内容。未知上传结果、字节不同、ref 移动即停，不能宣称发布成功。

- [ ] **选择唯一必要入口：workflow_dispatch 一次。** distribution 无 push 触发；本节点不额外开 PR、不触发 native-postgres 来重复旧任务、不为 R09 制造旁支“双绿”。若协调者已经为相同交付建立 PR／启动 distribution，先停止本节，查清已有 run 的实际 checkout 身份及归属后复用或重新明确唯一入口，不能 PR 与 dispatch 各跑一次凑结果。
- [ ] 通过 `gh api repos/wmqfl861/polymarket-alpha-lab/actions/workflows/native-distribution.yml` 核对 workflow 的 id/path/state=active；default branch 必须可识别此支持 dispatch 的 workflow。检查该 retained branch 所有状态的已有 runs（不只查 C），排除 queued/in_progress/waiting/requested/pending。原 concurrency 为 `native-distribution-${{ github.ref }}`、cancel-in-progress=true；冻结该 branch 的推送与重复派发直到终态，不取消其它人的运行。

```bash
gh run list --repo wmqfl861/polymarket-alpha-lab --workflow native-distribution.yml \
  --branch "$PAL_BRANCH" --limit 100 \
  --json databaseId,workflowDatabaseId,headSha,headBranch,event,attempt,status,conclusion,createdAt,url
test "$(gh api "repos/wmqfl861/polymarket-alpha-lab/git/ref/heads/$PAL_BRANCH" --jq .object.sha)" = "$PAL_C"
PAL_DISPATCH_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)
gh workflow run native-distribution.yml --repo wmqfl861/polymarket-alpha-lab --ref "$PAL_BRANCH"
```

上面的列表必须先检查再单次 dispatch，不能整段盲跑。权限／不可用／未知接受结果立即停止，不以改 workflow、换仓库或创建 PR 绕过。dispatch 返回成功只证明受理，不证明运行通过。随后用以下查询将运行唯一绑定到完整 C；零条为关联待确认，多条为歧义，不能取 latest 或再次 dispatch。

```bash
gh run list --repo wmqfl861/polymarket-alpha-lab --workflow native-distribution.yml \
  --branch "$PAL_BRANCH" --commit "$PAL_C" --event workflow_dispatch \
  --created ">=$PAL_DISPATCH_UTC" --limit 100 \
  --json databaseId,workflowDatabaseId,headSha,headBranch,event,attempt,status,conclusion,createdAt,url
# PAL_RUN 与 PAL_ATTEMPT 只能填上一步已唯一核实的真实数字。
gh run view "$PAL_RUN" --repo wmqfl861/polymarket-alpha-lab --attempt "$PAL_ATTEMPT" \
  --json databaseId,workflowDatabaseId,workflowName,headSha,headBranch,event,attempt,status,conclusion,createdAt,updatedAt,jobs,url
```

- [ ] 收到终态后核对 `headSha=C`、headBranch 正确、workflow 正确、completed/success，并读取同一 run/attempt 的 job、步骤及必要 proof/JUnit；不得跨 SHA／attempt 拼接。CI checkout 的实际提交必须是 C。

| 必查对象 | 验收要求 |
| --- | --- |
| `linux-kit` / Install locked test environment | 实际成功，保留 Python/runner/uv 真实版本；不能假定 CI 的 Ubuntu 24.04 等于发布 Ubuntu 26.04.1 tuple |
| `Assemble the qualified PG18 portable prefix` | 实际官方 key 下载、APT 验签与 PG18 prefix 装配成功；从现有日志保留首次错误、内部 retry、最终状态；没发生 retry 则写“未观察到”，不注入网络故障 |
| `Build and prove the actual Linux distribution` | 原测试清单真实执行成功；JUnit 中 `tests/test_project_postgres_distribution_native.py::test_build_and_run_actual_relocatable_kit` 必须执行通过、不能因 opt-in/缺驱动跳过；保留各测试统计和其它 skip 原因 |
| `Confirm tracked source unchanged` | diffcheck 与 tracked cleanliness 实际成功 |
| proof / kit uploads | `distribution-linux-proof-${C}` 的 log/XML 和 `linux-native-kit-${C}` 实际产出，记录名称、URL、字节/hash（读取到才填）；7 天 artifact 不是耐久交付来源 |
| `windows-kit` | 退休的 `if: false`，按预期 skipped 单列，不冒称通过、不恢复运行 |

PG 仅来自当前 workflow 的 binaries-only portable prefix，测试新建自己拥有的可丢弃私有集群；不连接服务器业务 DB、不采用系统已安装数据／角色／密码、不设置 PAPERSIM 业务 DSN。APT 当前仅钉 major `postgresql-18`，没有显式 patch 版本；从日志记录实际 `postgres --version`，不要虚称与发布 tuple 的完整 build 完全相同。此真实 CI 证明该次正常环境的集成，不是针对真实 libcurl 56 故障注入的证据。

## 6. 失败停止、回滚与回执

- 红灯阶段唯一允许的预期失败是新增 distribution 参数的目标断言失败。任何 collection、环境、权限、SSH 或工具错误单列；不得把“未读源码／未运行”变成源码 FAIL 或测试红灯。
- 当前计划作者不发 review verdict；计划审查／final review 未 PASS，或 Linux focused/full/compile/diffcheck/selfcheck/secret 未过，均不得 push／CI。无关全量失败也保留首错并交还对应 owner，本节点不越过三文件修复，不降低门槛。
- source/tree/file scope 不符、其它 writer 占用 DELIVERY_PLAN、涉及 R03 三文件写权、业务 DB 开关意外启用、敏感内容命中，立即停止依赖步骤。不得删除未知文件、强制应用补丁或从历史证据抹掉失败。
- dispatch 接受状态未知、run 不唯一、headSha/checkout SHA 不符、cancelled/timed_out/failure、关键步骤 skipped/NOT_RUN、缺 native proof/kit，均不算完成；保留该 run/attempt，不自动重派或 rerun。分类处理后如确需再次尝试，保留首次失败、内部重试、后续运行分别独立的记录，另行确认本节点范围及必要门禁。
- **未发布回退**：保留本节点工作树与 diff 给协调者；只有确认本节点独占且无后续 writer，才可按路径恢复本节点未提交修改。不要对 integration/R03 执行 reset/clean，不删除失败证据，不关闭他人的进程。
- **已发布回退**：retained ref 和原 C 不删除、不改写；如果需要撤销行为，用后续聚焦 revert 提交经过相同相关门禁与 fresh review，明确其 SHA，不能 force-push 或把原 run 当撤销后验收。没有业务库变更，因此不存在 DB 回滚／重放迁移动作。
- **实施回执必须返回**：C3、C、tree、retained ref；三文件完整路径与最终 bytes/SHA256、GitHub 回读一致性；作者 self-review 与两个独立审核的分离身份/结论；目标红灯、最终 focused/full/compile/diffcheck/selfcheck/secret 的实际命令/exit/统计与证据；实际 distribution run id/attempt/event/URL/UTC/headSha、linux-kit 各必需 step、真实 native proof 和 artifacts；所有首失败、重跑、skip/未运行与剩余阻塞。
- 交协调者继续既有 Q／R10 耐久证据发布和最终提示词流程，不以本地计划或到期 Actions artifact 作为必需交接文件唯一来源。**本节点不宣称 R03 完成、R09 最终双绿、FX-07 总验收、M0 出口或 V1 完成，不合并 main。**

**计划状态：READY for independent plan review。** 此状态仅指本计划可交给独立审查者；所有实施、测试、审核 PASS、发布和 CI checkbox 均尚未执行。
