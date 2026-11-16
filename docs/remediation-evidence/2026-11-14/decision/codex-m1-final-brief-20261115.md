# M1 整体终审任务（owner 委派）

你是 polymarket-alpha-lab 项目 M1 的**整体终审代理**（gpt-6-astra，思考 max），owner 指令："任务全部完成后需要通过codex审核，codex指定模型为gpt-6-astra/max"。只读沙箱：可读本机文件/git 对象/gh api 只读，禁止修改/创建/删除任何文件。输出经 stdout 保存为正式终审回执，末行单行 `VERDICT: PASS` 或 `VERDICT: FAIL`（附阻断项），随后一行 `DONE`。

## 终审对象

canonical GitHub wmqfl861/polymarket-alpha-lab main = **d83ab064**（本地 D:\Projects\polymarket-alpha-lab 同步；服务器经 repo 的 srv remote 可达，不打印地址/凭据）。M1 全链 15 提交（ca16ac47..d83ab064，见 git log）。

## M1 交付总结（协调者声明，你须独立核验）

九节点 + 两收尾提交，全部 fresh 独立只读复审 PASS（0 未决 P1/P2）：
1. **FX-08** 0198af16 decide_entry 单一入口（13 步闸门/47 拒绝原因/FX-13 方向纪律/严格桥；P2 修复后 delta PASS）
2. **FX-10** 304a241a 通用候选构造器（18 冻结定义 AST 逐字不变；4 夹具逐位回归）
3. **FX-11** 2713c6ca 全候选评分+OD-G A–F（10-30 复现 23.30%/51.1%/12.22%/Brier，±1.5pp）
4. **FX-09D** 设计（外部 b88161a1…，两轮复审：v1 FAIL→v2 PASS）
5. **FX-09S** 32f98ee1 受管 schema/store/迁移（30 一次性 PG native 证明；slug 幂等键裁决接受）
6. **FX-09L** 795ceb58 桩补全/历史导入/CI 接线（native 237；六偏差裁定 5 ACCEPT+1 条件）
7. **FX-12** a3fdc10a 快照注册+取证重放（51 native；纯 SELECT/篡改捕获）
8. **final CLI** ebe542e0 evaluate/replay 子命令（native 28；零驱动 import）
9. **合成** 29f043f7 一次性 PG 端到端五步全 PASS + DELIVERY_PLAN §78
10. **CI 整改** 49951207（惰性驱动导入/native 感知断言/pal_owner CREATEDB）
11. **加固** d83ab064（TIME_WAIT 就绪等待推广至全部 4 个 OLD bind payload + 5 处 admission view 回显）

**双 CI 终态（同 SHA d83ab064，attempt 1，event=push）**：Offline run 43795350447 success；Native run 43795350382 success（research/dispatch/storage/papersim 四分区全绿+聚合绿；windows 设计性 skip）。

## 终审核验清单（逐项核验后裁定）

1. **计划符合性**：读 M1 计划 D:\Projects\pal-remediation-plans-20261113\M1-next-nodes-plan.md（28,092 bytes，SHA256 0a48b7bc6e000f3df693431815a842291079bc7498f57248c97727031e55e47f）——M1 交付是否实现其 §2 节点/写域、§3 各节点设计要点、§6 合成出口可本地验证项？明确登记的缺口（§78.3 七项：§7.5 视图延后/生产导入未执行/连续运行未做/计数口径注记/CodeGraph 状态/回执存档）是否与计划边界一致、无冒充？
2. **铁律核验**（git show 对象级）：PostgreSQL-only（新 store_psycopg 是唯一新连接器，白名单恰一行）；paper-only/report-only/readonly 无违例（rg 新模块无实盘/凭据/下单路径）；冻结面未动（supabase/migrations 70 条、V1 源码、gates/阈值、OLD 2b20002c）。
3. **双 CI 独立确认**：gh api 拉 43795350447/43795350382 两 run——headSha=d83ab064、attempt 1、结论 success、四分区+聚合逐 job 核对。
4. **抽样深检**（你自主选 ≥3 处）：如 FX-08 的 FX-13 方向纪律（terminal_yes_probability 调用面）、09S 的 DSN 铁律（validate 先于连接）、FX-12 replay 纯读、09L 分币守恒数字（743.79+561.41=1305.20）、加固后 4 个 bind 点等待齐全。
5. **已知开放项**（不影响 M1 工程出口但要如实列出）：`_old_cli up` bind 点同构暴露（复审裁定后续节点处理）、§7.5 视图、生产导入授权、连续运行 M2/FX-17。
6. **结论**：M1 作为工程交付（非策略验证、非 M2/M3）是否 PASS。

## 边界

不改任何文件；不连业务库；不触凭据/公网地址输出；不因"计划外发现新问题"无限扩大——新问题按 P3 列出即可，只有 P1/P2 阻断才 FAIL。

## 终审整改记录（你上轮 FAIL 后的修复链，纳入核验）

你上轮终审 FAIL 的三项 P2 已全部修复并过 fresh 独立复审 PASS（回执见 repo 内或协调者会话记录）：
- P2-01 → commit 0ca71e42: cli.py LEFT JOIN settlements + EXIT→EXITED+账本 pnl + natural_outcome 独立字段；终审复现场景（250@0.50退出@0.30→毛-100/净-111.50/退出1）已转正式测试。
- P2-02 → 0ca71e42: ConcentrationMetrics.net + criterion E 读 top_market_net_share；终审四市场场景（毛29.99%/净30.1869%→FAIL）已转正式测试；10-30 毛口径锚点保留。
- P2-03 → 0ca71e42: yml papersim 矩阵恰+2文件（九文件精确清单）+PAPERSIM_FILES pin 同步。
- 后续: d83ab064 修复 CI 共享集群测试隔离（快照 count 改 digest 范围查询）。
- 修复提交本身经 fresh 独立只读复审 VERDICT: PASS（独立复现终审场景→修复验证→测试覆盖三段确认）。
- 最终双 CI（同 SHA d83ab064，attempt 1，event=push）: Offline run 43795350447 success + Native run 43795350382 success（四 Linux 分区全绿含 papersim 九文件矩阵首次全绿）。
- CI 证据获取指引: gh api repos/wmqfl861/polymarket-alpha-lab/actions/runs/43795350447/attempts/1/jobs?per_page=100 与 .../43795350382/... 可用（如 gh 不可达，可读本地 git log d83ab064 + tests/ 下测试文件核对断言存在性）。
