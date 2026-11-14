# R03：C3 OLD seed errno98 的下一次有限取证计划

状态：PLAN_REVIEW_PASS（fresh 独立复审，无阻断）；已按复审意见应用修正：P2-1 STOP 边界引用改为 `R03-version-port-followup-plan.md:17`；P2-2 增加本机 18.6 前缀与 CI 18.7 的版本标注及不可外推声明；P3 澄清 `_psql` 聚合计数口径、A 步端口各经一次 `pick_port()` 互异且非 55432、全程禁用 sudo。本文件不授权执行：实验 A/B 须待 fresh 独立脚本复审 PASS 后由协调者分派唯一 invocation。2026-11-14 本 worker 仅只读核验并创建本计划，未启动 PG、机制实验、probe 或 CI，未改源码、测试、配置；不继承旧一次运行的批准。

## 固定来源与已知边界

- C3：`6add9b041754600109e17e6aa05b0cb99aaface6`，tree `22d2a7b79d4ae1d44c41abb5fccbd23afae53fe9`。
- OLD：`2b20002c83ee33acb95fb2ca3de841f3e883ebbf`，tree `d6f6750b1068a3c75ab6249d5ca4f1ef7e010ee4`。两对象及 tree 本地只读核对一致。
- 读取位置：`D:\Projects\polymarket-alpha-lab`，当前 HEAD 是 `37b288956187de404ee0047bc0a5beeccbe9dbf6`；源码均从固定对象 `git show` 读取。现行 AGENTS 与 C3 无差异。CodeGraph 命令不可用，未初始化索引。
- 未来运行位置仅 Linux：`/home/ubuntu/pal-m0-startup-20261113-yx2fyoje/checkout`；启动前必须验证 C3/树和 clean，不能用 Windows 工作树充当 C3。SSH 目标仅从既有 `remote.srv` 在内存解析，不打印地址、不读密钥或环境内容。
- 已读 C3 DELIVERY_PLAN 状态板、§55、§77.3–77.5、§77.8：V1 未激活，OD-A 允许 Linux 原生测试维护，R09 要求同一最终 SHA 的双绿和独立复审。计划不更改这些门槛。
- 以下 CI 为协调者已核实输入，本 worker 未重查/重跑：C3 Offline `43551531524` success，41461/122/20；Native `43551531643` attempt 1，storage job `132314854354`，分区 311 passed/2 skipped，版本步骤 1 failed/43 passed，research/dispatch/papersim 成功，aggregate failure。OLD seed 首 errno98/`project_postgres_port_in_use`；退出后快照 OWNER_UNKNOWN，IPv4 local TIME_WAIT=3、peer TIME_WAIT=70，IPv6 无行，cleanup stopped。原 OSError 栈 NOT_EMITTED。
- 旧一次诊断 NOTREPRODUCED，端口 32088，local TIME_WAIT/LISTEN=0，peer TIME_WAIT 0→73→88。这是不同运行，不能抵消 C3 首败，亦不提供本次执行授权。

## 已证实的调用链与未知

以下 `H` 指 C3 `tests/test_project_postgres_version_switch_native.py`；`S` 指 OLD `src/polymarket_alpha_lab/project_postgres/server.py`。

1. `H:914–928` 顺序是 OLD install-runtime → init(63) → 再 init 必须拒绝 → status 必须 stopped → 原 seed。`S:189–193` 是第一次 init 的无 reuse bind；重复 init 在 `S:187–188` 因 home 已存在先拒绝，不再 bind。`status` 的 stopped 路径只查状态，不启动引擎或连接 SQL。初选 `pick_port()` 只 bind/close，不 listen/connect，不产生 TCP TIME_WAIT；其内部最多 64 候选是既有初选行为，不是获准失败后换端口。
2. 首次 init 经 `S:220` 启动，`S:224` 迁移，`S:227–233` finally 调 `_stop()`；后者先完成身份和 active-count 的 psql 子进程，再 `pg_ctl stop -m smart -w -t 60`。`files.command()` 等待子进程返回。成功 stopped 不保证内核没有 TIME_WAIT。
3. seed 链为 `H:928→883→_OLD_RUNNER:250→_SEED_PAYLOAD:471 db.session()`，再 `S:296→_start:144–148`。此处 AF_INET/SOCK_STREAM 的 bind 未设 reuse，先于 `S:149 pg_ctl start`。同一路径没有第二个 seed bind；不把首次 init、选端口和 seed bind 混为同一个异常现场。
4. candidate 在此前只用于归档验证、目录校验及 runtime 版本检查，没有对该新 cluster 启动或 SQL 操作。真正 candidate 会话在后续 lifecycle 阶段；失败后的 cleanup 使用 C3 `ProjectPostgres.down()`，发生在首错之后。C3 自身 `_start:151–152` 已设 POSIX reuse，不能倒推 OLD 也有该行为。
5. `OLD files.py:19–20` 是 `raise ProjectDatabaseError(code) from None`：原 OSError 仍在 `__context__`，默认 traceback 被 suppress。C3 runner `H:256–259` 只提取 errno；`PAYLOAD_SOURCE_OK` 在正常运行后才输出，故其缺失是首异常后的结果。增加 pytest traceback 长度不能恢复被 suppress 的 context。
6. 原证明明确包括 OLD stopped→自主 session 启动→seed→stopped（`H:927,928,946`），之后还由 OLD snapshot 再启停（`H:950–954`），以及后续 OLD up/rollback。提前用 candidate 启动、把 seed 变为 borrowed session、缩小 OLD 路径、替换其 bind 或加等待都会改变证明，不能作为本轮修复。
7. 协议关闭核对：PostgreSQL 18 §54.2.9 规定 frontend 发送 Terminate 后关闭，backend 收到后关闭；REL_18_6 `fe-connect.c:5220–5242,5254–5275,5301–5306` 实际是 PQfinish→发送/flush Terminate→pqDropConnection/socket close；`postgres.c:4990–5006` 收到 Terminate→proc_exit。两端 TCP close 存在时序竞争，不能称 smart stop 必然使 server 主动关闭。REL_18_6 `pqcomm.c:569–580` 的 POSIX listener 设置 reuse，与 OLD 预检不同。这些是官方源码/协议依据，不是本机已装二进制的 FIN 顺序实测。

参考：<https://www.postgresql.org/docs/18/protocol-flow.html#PROTOCOL-FLOW-TERMINATION>；上述三个文件位于 `https://raw.githubusercontent.com/postgres/postgres/REL_18_6/src/` 下相应目录。此次仅网络只读源码文本，未保存或执行外来代码。

排序假设：① OLD no-reuse 对 local-service TIME_WAIT 误判；② 同端口真实 listener、bound socket 或短暂竞争；③ 现场不是所推定 bind/生命周期前提不成立。当前 errno 与退出后计数支持①，但不能证明三条 TIME_WAIT 的 owner、首次 bind 时状态、FIN先后，亦不能排除②。peer-only TIME_WAIT 不足以支持①。

## 新计划：两个有界步骤，均只做一次

### A. 零 PG 的合成 socket 机制对照

只在自有 loopback 新端口上，顺序做两个预声明小场景，每场景一条自有 TCP 连接。使用 Events/EOF/线程 join 协调，单个 socket 操作最多 2 秒，整步最多 15 秒；不用 sleep、轮询等 TIME_WAIT 消退、随机重跑或更换失败端口。两场景端口各经一次现有 `pick_port()` 独立选取，断言彼此不同且均不等于 55432；与后续 PG 的 P 不重用（B 的 no-reuse 初选会自然避开仍在 TIME_WAIT 的 A 端口）。

- server 先关闭：listener 在 bind 前设置 SO_REUSEADDR=1（匹配 PG POSIX）；记录 getsockopt 实值。连接双方交换完固定短消息并读尽；accepted server 执行 shutdown(SHUT_WR)，client 必须 recv EOF 后才关闭自己的发送端，server 读至 EOF 并关闭 accepted socket，最后关闭 listener。不得用 SO_LINGER/RST。在此同端口立即各做一次新的 no-reuse bind、reuse bind，记录 errno/成功并关闭，不 listen、不重试。
- client 先关闭对照：相同 listener 设置；client 先 shutdown(SHUT_WR)，server 读到 EOF 后才关闭发送端，client 读至 EOF，再关闭两端及 listener。相同两次 bind 对照。
- 每个场景在 bind 对照前后只取该服务端口的 `/proc/net/tcp{,6}` 状态计数，明确 local/peer；记录主动关闭端、EOF顺序、实际 reuse 值、无活 listener 的结果及 monotonic 时刻。预期 server-first 为 local TIME_WAIT/no-reuse errno98/reuse 成功；client-first 为 peer TIME_WAIT、服务端口 no-reuse 可绑定。预期不是伪造的通过条件；任何偏差原样记 CONTROL_UNEXPECTED，不追加场景。
- 这一对照仅证明 Linux socket 机制与端点区别；不模拟或认证 PostgreSQL 协议、不能归属历史 CI socket。若执行/观察故障、异常结果或 cleanup 未完成，B 记 NOT_RUN，停交协调者。

### B. 一个全新自有 PG 上的真实 OLD 前缀

**启动前只读门槛。** 复用已装环境，不安装、不下载、不重新装配。Python 候选为已有 `/home/ubuntu/pal-m0-startup-20261113-yx2fyoje/environments/r03/bin/python`；保留 venv 路径，不 resolve 成裸解释器。仅核对其 Linux/版本/依赖来源，缺失即 BLOCKED。PG prefix 为同根 `environments/pg18-portable`；已有 inventory `environments/pg18-portable.inventory.tsv`，186507 bytes、SHA256 `812d410a15f218b432c2ea3ed531a8e266509e92fd533ceeebc58e1f1af651e4`、1706 文件/49889272 bytes。按该清单验证内容，五工具需同一 18.6 精确版本且无链接；不能凭旧报告认为当前已复核。版本标注：本机 `pg18-portable` 前缀为 PostgreSQL 18.6（源码核对基线 REL_18_6），而 C3 CI Native 全分区使用 runner 侧 PostgreSQL 18.7（18.7-1.pgdg24.04+2）；因此实验 B 是本机 18.6 上的机制复现，不是 CI 18.7 环境复现，其判读不可外推为 CI 已证明。不开系统或线上库。核对 `/proc/net/tcp{,6}` 完整有界读取可用、空间足够；任何门槛不符均在 PG 前停。

**隔离与原路径。** 在 ROOT 下分别新建非重用的 `task-tools/r03-next-*`（只放经审核的外部 driver/observer）、`tasktmp/r03-next-*`（验证归档、payloads、Original Project）和 `evidence/r03-next-*`（少量白名单结果）。执行 cwd 为 task 的 neutral 目录，Python `-I -B`；不从提取目录启动。保留 harness 的完整 archive 验证、原 OLD/fixture、70/63/7 校验及来源断言。调用现有 `prepare_verified_archives_and_private_root()` 一次，记录唯一 P，断言 20000≤P≤32767，P!=55432。此后不重新选 P；不将 helper 的初选重试隐瞒为单候选。

按 `H:916–946` 原样调用并保留全部断言，精确停止在 seed 的 records/status_after 校验之后，不调用 snapshot 或七阶段后续证明：

1. `_old_cli(... install-runtime --from-directory prefix)`，runtime_installed。
2. `_old_cli(... init --port P)`，63 迁移；包含 OLD 原 finally stop，不加另一轮 down。
3. 同参数再次 init，exit 1 且 existing_data_not_reinitialized。
4. OLD status，stopped。
5. `_old_payload(rig, 'seed.py', _SEED_PAYLOAD, str(original))`，仍执行原 runner/payload，仍要求 PAYLOAD_SOURCE_OK、原合成记录/三个安全标志/不完整历史拒绝/status_after。若成功，本步仅 NOTREPRODUCED；不继续完整 suite。

**只观察，不修改 OLD。** 外部 observer 的实现必须在运行前另交 fresh read-only review；本计划不宣称尚未写出的脚本已审核。观察入口仅包围 harness 的 `_run` 启动边界，把原 `_OLD_ENTRY`/`_OLD_RUNNER` 文本交给隔离子进程外层 bootstrap；原文本与 `_SEED_PAYLOAD` 从 C3 提取并逐字节/哈希验证，exec 的编译文件名保留 `<string>`，传给原 runner 的 sys.argv、src 注入、cwd、环境和退出码不变。不 monkeypatch socket/产品函数、替换异常、生成成功 marker、重写 OLD 或把异常改返回值。外层必须保证 original runner 只执行一次，并在 finally 恢复 trace。

- trace 仅对精确已验证 OLD `server.py` 的 `_start`、`initialize`、`_stop`、`_control`、`_psql` 事件生效。禁止转储 locals/argv/env/info；从 `info` 只核对 port==P，从 `_control` 只读 action 枚举，从 `_psql` 只记录返回事件次数，不读 SQL/DSN/返回正文。callback 内部任何观察异常必须捕获、标 OBSERVER_UNAVAILABLE 并禁用该观察，不能向产品帧抛出；原执行/首错照常保全，诊断证据判不充分。
- 第一 OSError 在 `_start` 的 exception event 同步记录：异常类型、整数 errno、OLD 相对文件/函数/行号组成的帧列表、monotonic 起止时刻和 P 的 proc 计数。遇到随后的 ProjectDatabaseError，仅允许其固定 reason code，并显式遍历 `__context__`/`__cause__` 的类型、errno、帧元数据及 suppress 标志；记录其 context 是否就是首次捕获的 OSError。不要用 format_exception 默认行为，也不要输出异常 repr、任意消息、源行或 locals。这是对 C3 NOT_EMITTED 缺口的必要补充。
- 采样点：pick 后、init 第一次 bind 前、OLD `_psql` 仅聚合计一次返回总数（init/stop 合计上限 96 次，不逐次发事件、不逐次读 proc；smart stop 前的状态由 `_control('stop')` 调用前快照覆盖，用于辨别 local TIME_WAIT 是否在 smart stop 前已出现；seed 的 SQL 不采样）、smart-stop 调用前后、status stopped 后、seed `_start` bind 前/首异常时、子进程退出后、cleanup 后。成功时只记录控制路径和有限计数，不为采样增加 SQL/connect/bind。seed 启动前的父进程检查若存在实际 listener/其他不明状态，照实保全并停止后续业务，不接管/强停该 listener；已进入产品的 trace 只观察，不注入中断。
- 每次每个 proc 文件最多读 65537 bytes，超 65536、部分行、格式异常、权限问题均 UNAVAILABLE，绝不记零。只在内存解析并输出该 P 的 local/peer 各 TCP 状态数量；不得落盘原始 proc 行、地址/编码地址、inode、PID清单或其他端口。不用 `/proc/*/environ`、全机 ss/lsof、抓包、ptrace、namespace 或 sysctl。快照和异常有时间差必须记录，所有非独立证实归属均 OWNER_UNKNOWN。
- seed 原 runner 未到来源 marker 时，外层仅附加 `loaded_project_modules_within_fixed_old` 布尔核对（采用原 runner 的路径规则），不能补写 PAYLOAD_SOURCE_OK。这样定位失败，不伪造原 provenance 成功。

**时间与 I/O。** B 的业务前缀总墙钟最多 900 秒；保留原代码内 initdb/psql/pg_ctl 的超时，不加等待策略。外层 driver 启动的每个 child stdout/stderr 各最多 256 KiB 在内存；保留返回字节给原断言，不直接落 raw stderr。observer 总事件≤128、每条≤4096 bytes（`_psql` 与 `_control('status')` 只以聚合计数各占一条，不逐调用发事件，避免撞预算）；proc 总读量≤17 MiB；脱敏证据总量≤1 MiB。超时/超限即执行失败，不运行后续业务、不重试；仅终止该次 driver 所拥有的直接 observer/CLI 子进程，不能 kill PG 或其进程组，更不能碰共享服务。必须进入下列自有 cleanup；未能停止的任务进程单独记为阻塞。不要沿用旧 driver 的无界 ss/capture 或把普通退出后计数标成“已证自身 TIME_WAIT”。

执行入口应是经后续实施/审核固定的一个外部 driver，参数为上述 repo、固定 C3/OLD、prefix、Python 和新 tools/data/evidence 根；不从旧带审批字样的 driver 直接启动。本阶段未创建该 driver、未给虚构哈希/已执行命令。协调者在执行分派中必须填实际新目录、脚本 SHA256 和唯一 invocation；缺任一项不启动。内部分阶段审核计划不冒称 GitHub-first 完整交接；若需对外委派执行，先按项目规则发布不可变交付及验证字节。

## 写范围、cleanup 与首错保全

本阶段唯一写文件是 `D:\Projects\pal-remediation-plans-20261113\r03-next-diagnostic-plan-20261114.md`，创建前确认不存在。未来获明确分派后的写域只限上述三个新临时目录；固定源码/测试/OLD/fixture/migrations/threshold/10 selfcheck/规则/模型不变。不给旧计划、旧证据或旧 driver 覆盖写权限。不运行生产探针、读原有凭据/DB日志、业务文件持久化替代、联网模型、commit/push/CI。全程禁用 sudo 及一切等价提权执行，不以提权读取文件或调整系统参数。

A 的 socket、线程各自在 finally 关闭/有界 join。B 无论成功/失败仅调用一次现有 `stop_owned_disposable_instance_preserving_failures(rig)`，该 helper 用 C3 down，确属原证明已有清理行为；再 OLD status 核验 stopped。cleanup 单列最多 300 秒，不能覆盖 first failure 或改 verdict；失败/超时即 STOP，不 force kill、不反复 down、不删除 cluster。已启动的 driver/observer 都按其自有 PID 归还并记录状态，不能以“主 driver 退出”声称 PG 已停。

成功 stopped 后也不读取/上传任务 credentials、cluster、备份或 server.log；保留私有任务根直至协调者确认白名单证据齐备，再按确切自有路径清除。源码与 prefix 前后哈希不变、原始首败和诊断失败/cleanup失败分别记录。返回一个精简 JSON 和一个仅帧元数据的首错文本即可，不新增报告系统；未执行步骤明确 NOT_RUN。

本轮已向协调者登记只读过程偏差：初次工具原文显示仓库已有公网地址，后续输出做过滤，本计划不复述；另有本地切片越界/工具超时，无 DB 或实验执行。此项不得改写为全程零地址回显。

## 可关闭的事项、不能关闭的事项与后续决策

| 实际结果 | 可得结论/下一步 | 不可宣称 |
| --- | --- | --- |
| A 两控制符合，B 未复现 | 该 Linux 的 TIME_WAIT/no-reuse 机制成立；一次真实前缀未复现 | 不能关闭历史 C3 errno98、R03、Native 或 M0 |
| B 同步捕获 OLD:146 errno98、上下文链、local TIME_WAIT且无已观察活 listener | 可以关闭“异常发生在哪一 bind/为什么 marker 缺失”的证据缺口；与 A 联合支持 OLD 预检缺陷类别 | proc 无活 listener 不排除其他 bound socket/竞态；归属不明时不能称“已证明 CI 自身 TIME_WAIT” |
| B 发现 listener、未停机、不同栈/errno、UNAVAILABLE、超时或超限 | 保存第一现场，按不同原因或证据不足 STOP | 不把未知等于零，不加 reuse/重试/放宽断言 |
| 足够证据确认 OLD 拒绝其正常退出连接的 TIME_WAIT | 执行旧 `R03-version-port-followup-plan.md:17` 的 **STOP 并报 owner**；给固定版本/栈/时刻/实验结果 | 不在冻结 OLD 中补 reuse，不借 candidate 启动凑绿，不偷改 proof |

原 STOP 边界不是“连诊断都不能继续”：本次新有界取证可在 fresh review 与另行分派后做。真正超出现有 OD-A 测试维护授权的决定是修改/重选冻结 OLD、引入兼容启动替代其生命周期、取消 OLD 冷启动义务或改变验收结论；若还需 V1 产品改动也超出 OD-A。一般“继续完成任务”不自动等于明确选择这些改变。确认缺陷后先报具体阻塞和需要改变的哪项证明，由协调者取得 owner 的具体决定，不能直接修改测试规避。

当前唯一能保持前后证明的 harness 方向是**只增诊断**：直接输出 suppressed OSError 的白名单帧/errno并保持同一异常对象、bare raise、退出码、原 provenance 断言、全部生命周期/数据断言不动。改前=原 OLD 重启/seed 失败，原因栈不可见；改后=同样失败，原因栈可见。现有 `H:1392–1413` 已检查异常/context/traceback保全，未来若实现还需补“帧白名单、observer失败不遮盖原错”的精确测试及独立审核。本阶段不实施；它能关闭可观察性缺口，不能修复 OLD bind 或关闭 Native。

R03/Native/M0 最终关闭仍需未弱化原证明的最终 SHA 全门禁、同 SHA Offline/Native（含 storage version-switch 与 aggregate）成功及 fresh 独立复审。此计划、A 的绿、B 的一次绿均不替代这些条件。
