# mirror-verify-20261114 — server-mirror 清单与服务器现行脚本树一致性复核报告

- 日期：2026-11-14
- 取证 worker：只读复核（七项本地复核第3条 / 九出口第4条的"确实来自服务器"来源证据）
- 约束遵守：未修改服务器被检文件、未读写 .pgpw/凭据/业务 DB、未重打包 tarball、未改清单文件；服务器侧唯一写入 = 新任务目录 `~/mirror-verify-20261114/`；本报告不含公网 IP 与凭据。

## 1. 清单解析（格式与映射规则）

- 清单来源：`git show 6add9b041754600109e17e6aa05b0cb99aaface6:docs/paper-sim/server-mirror/MANIFEST.sha256`
- 头注 8 行（`#` 注释），数据行 415 行（第 9–423 行），格式与头注声明完全相符，无需中止。
- 列（TAB 分隔）：`sha256 <TAB> size_bytes <TAB> server_mtime_utc <TAB> server_path_relative_to_/home/ubuntu/paper-sim`
- 相对路径 → 服务器绝对路径映射：`<rel>` → `/home/ubuntu/paper-sim/<rel>`（头注明确根为 `/home/ubuntu/paper-sim`，即 `~/paper-sim`）。
- 全部 415 行通过严格格式校验：sha256 为 64 位小写 hex、size 为纯数字、mtime 为 `YYYY-MM-DD HH:MM:SS`、路径为安全相对路径（无前导 `/`、无 `..`）；无重复路径、无重复 hash。
- 脱敏条目口径（关键）：
  - 头注称 411 行与服务器逐字节一致 + 4 行脱敏。经逐字节核验（`git show 6add9b0…:docs/paper-sim/server-mirror/<path> | sha256sum`），这 4 行的 sha256 列记录的是**入库脱敏后内容**的 hash，而非服务器原件 hash：
    | 清单相对路径 | 清单列（=脱敏后 hash） | 服务器原件期望 hash（REDACTIONS.md "original sha256"） |
    |---|---|---|
    | round29/raw/write_scan.py | 9d078a8cdcd753c5066c480aa2b35e491c90f0cb1cf1752780ab604d50517ab7 | 93ed8a73524809356e0bdc2804aa3133b5bcf2bd62ab44cfd29e12183e2be9ff |
    | round39/eredivisie_validate.py | 2d86775882a75f0f92471ef33bf9b6d5dc73bb2a970945ee9cae8edbcb78d39c | 4f58c43b1c40e2e8c949b078eb9eeacbf6a9e7b6ffe3a705ea0c99ab1139a9b9 |
    | intl/wp_intl3/polymarket_alpha_lab/papersim/league_strength.py | 1733bbd90f6833c14d81d6223d408124c23a871c93065657a1a9a2786df30cd8 | d76b25e84b0b7f5a25f9b6a3af7fabde7efe66b5dd3a4f3b411dbd10bd2817a0 |
    | tools/fotmob_validate.py | d0e049f3b24b316f268755ba08d03fcd055fb2daa3775b91aeb669dc8dd1fcb4 | 6e8be5cfa874047a97f3a926e65dca3a464392e2d07cc6dd803be8c04ed11cb0 |
  - 因此服务器比对规则：411 行按清单 hash 比对；4 行按 REDACTIONS.md 原件 hash 比对（REDACTIONS.md 明言"original bytes remain on the server"）。

## 2. 服务器侧执行方法（只读）

- 服务器：SSH 目标自本地 git remote `srv` 内存解析（地址不落文、不打印）。连通性 OK，python3 3.12.3，`~/paper-sim` 存在。
- 任务目录：`~/mirror-verify-20261114/`（执行前确认不存在，新建）。内容：
  - `manifest-rows.tsv` — 清单 415 数据行原样上传（本地暂存件与服务器件 sha256 均为 `a32ba511c047b5a67115e50a70a302ebde333c5892bd38784c05edff6aa9bfc2`，传输完整）。
  - `verify.py`（sha256 `6533f527fb6a39d13aab1bd15e318bd6c29a5cac30c39973af1ffb8166370e4d`）— 以 `python3 -I -B` 运行的比对脚本：只读打开被检文件计算 sha256；不打印任何文件内容；结果写回任务目录。
  - `results.tsv`（sha256 `e9c7a3328281b34101e36683e04122713d27a819ccf4d906a90924f34f7eab60`）— 逐行结果。
  - `summary.txt`（sha256 `59410fa3f9911eb04b913e7488f1c0b25e868db9b6d39216a2d2fdfe7603c661`）— 统计与不匹配清单。
- 被检文件全程只读（`open(...,'rb')` 仅有 sha256 与结构化 diff 统计）；对 `wp_intl_validate.py` 的差异分析仅输出 hunk 数、单行性、100→50 纯度等布尔/计数结论及行号定位，不输出文件内容。

## 3. 统计结果

| 指标 | 数值 |
|---|---|
| 清单总数 | 415 |
| 逐字节一致（非脱敏行，按清单 hash） | 410 |
| 脱敏行与服务器原件一致（按 REDACTIONS.md 原件 hash） | 4 |
| 不匹配 | 1 |
| 缺失 | 0 |
| 合计口径（一致 410+4 / 总 415） | 414/415 |

与 2026-11-12 入库时点记录（"411 行逐字节一致"）对照：非脱敏 411 行中现有 410 行仍逐字节一致，唯一漂移即下述已记录变更。

## 4. 不匹配明细（仅 1 条，缺失 0 条）

| 项 | 值 |
|---|---|
| 路径 | intl/wp_intl3/wp_intl_validate.py（服务器 `/home/ubuntu/paper-sim/intl/wp_intl3/wp_intl_validate.py`） |
| 清单 hash（mtime 2026-11-12 09:02:27, size 99503） | 0f93da6c13c519cf9d860d14c335c964b1597091e2dd7093bb3169cc0e39f7bf |
| 实际 hash（mtime 2026-11-14 01:19:29, size 99500） | 6b8ac548b85d8993df5c31c92702c748f39c17ecb55bcc7d52120bcd6676d700 |
| 判定 | **已记录变更**（2026-11-14 分页 limit 100→50 修复），非未知漂移 |
| 证据 | 备份 `wp_intl_validate.py.bak-20261114` 存在且其 sha256 = `0f93da6c…` 与清单 hash 完全一致（清单时点字节被原样保留）；`.bak` 与现行的 diff 恰为 3 个 hunk，全部为单行改动，每处仅把一个数值 `100` 改为 `50`，无其他 token 变化、无插入/删除行；定位在修复前副本第 416 行（`"limit": 100`）、第 430 行（`len(page) < 100` 判断）、第 432 行（`offset += 100`）——即分页 limit 参数、短页判定与偏移步进三处配套修改，与已记录的"分页limit 100→50三处"描述一致（三处中仅第 416 行字面含 "limit"，另两处是同一分页尺寸的算术配套行）。 |

除上述 1 条外，无其他不匹配或缺失条目。

## 5. 结论

1. **服务器现行脚本树与入库镜像一致**：415 条清单项中 414 条与服务器逐字节一致（410 条原样行按清单 hash + 4 条脱敏行按 REDACTIONS.md 原件 hash）；唯一差异 `intl/wp_intl3/wp_intl_validate.py` 为 2026-11-14 已记录的分页 limit 100→50 修复，清单时点字节完整保留于 `.bak-20261114`，差异内容经结构化核验恰为该修复本身，无未知漂移、无缺失。
2. 七项本地复核第3条/九出口第4条所需的"确实来自服务器"来源证据成立：现行服务器树与入库清单（除已记录修复外）逐字节吻合。
3. 历史 tarball `papersim_mirror.tgz`（sha256 `3fff20269ac6edfcaaf151e47e9dd5fcb3eae9b2b1846f710cb0bd2266ed5983`，1054525 字节）在本地与服务器常规路径仍未找到，**来源 UNKNOWN 状态如实保留**；本次未重新打包、未改动清单。该 UNKNOWN 不影响第 1 条的现行一致性结论（本结论基于逐文件哈希比对，不依赖 tarball）。

## 6. 证据指纹汇总

- 清单源：commit `6add9b041754600109e17e6aa05b0cb99aaface6` 路径 `docs/paper-sim/server-mirror/MANIFEST.sha256`（头注 8 行 + 数据 415 行）
- 上传清单数据行（本地=服务器）：`a32ba511c047b5a67115e50a70a302ebde333c5892bd38784c05edff6aa9bfc2`
- 服务器任务目录件：`verify.py`=`6533f527fb6a39d13aab1bd15e318bd6c29a5cac30c39973af1ffb8166370e4d`；`results.tsv`=`e9c7a3328281b34101e36683e04122713d27a819ccf4d906a90924f34f7eab60`；`summary.txt`=`59410fa3f9911eb04b913e7488f1c0b25e868db9b6d39216a2d2fdfe7603c661`
- 唯一差异文件：清单 `0f93da6c13c519cf9d860d14c335c964b1597091e2dd7093bb3169cc0e39f7bf` → 现行 `6b8ac548b85d8993df5c31c92702c748f39c17ecb55bcc7d52120bcd6676d700`（备份 `.bak-20261114` = 清单值）
