# UPDATE-SPEC — goose sourceReader 刷新规范

## 基准与范围

- 仓库：`/Users/vincent/workspace/16_AI/goose`（monorepo，`crates/*` 15 个 crate）
- 基准提交：`main@71dd9a9aa2344247a51bc349f4d0b97c2dbff4bd`（工作区干净：仅 `docs/`、`.codegraph/` 未跟踪）
- 当前 HEAD == 基准提交（`git rev-list --count 71dd9a9aa..HEAD` = 0）→ **0 提交漂移**
- 核实日期：2026-11-18
- 文档目录：`docs/sourceReader/`；本库为**四层阅读库**（L1 骨架 → L2 全路径 → L3 主链路 → L4 主题补齐）

## 定位记法（本库约定）

- 正文锚点用 `file.rs · Symbol+N`（文件 · 符号 + 偏移，`+0` = 符号定义行）。
  - 2026-11-18 已把全库「绝对行号」记法升级为「符号 + 偏移」：145 处 `file.rs +N` → `file.rs · Symbol+N`，另 55 处裸 `（+N）` 续引用按上下文解析为所属符号。
  - 偏移相对符号定义行；`+N` 用 `sr_tools.py`/`anchor_rs.py` 实时重算，代码移动后引用不失效。
- 目录前缀用于消歧：`crates/goose/src/agents/services.rs · reply+0`；无前缀时依赖上下文（如 `provider.rs` 在 05 指 `crates/goose/src/acp/provider.rs`）。
- 源码索引段（文末 `文件：符号 +0`）只给映射，不承诺行号稳定性。

## 内容红线

- 禁臆测：事实（有无缓存/字段/默认值/表/调用链）必须回当前工作区代码检索或定点阅读；无法证实标 `[源码未确认]` / `[源码未找到]` / `[推断]` / `[待运行验证]`。
- 当前态优先：正文只描述当前实现；迁移/决策背景放变更记录。
- 先总结后分层：每篇先结论速览，再生产视角（谁触发、条件、输入、环节、输出、失败表现），后开发视角（入口、调用链、字段、存储、异常）。
- 图表与列表达标：实质性专题至少一张生产流程图 + 一张开发图 + 结论/条件/映射三张表。
- 生产层无源码定位表达；开发层有当前工作区源码证据。
- 两处合法「占位」除外：00 的 `TODO/TBD` 是规范条款本身；05 的 `...` 是 Rust 函数签名省略（`fn from_env_with_working_dir(...)`）。

## 本库结构（9 篇）

| 篇 | 层级 | 主题 |
|---|---|---|
| 00 | meta | 规范与定位约定 |
| 01 | L1 | 系统骨架（进程/组件/主流程） |
| 02 | L2 | 一次真实操作全路径走读 |
| 03 | L3 | 主链路逐跳拆解 + 时序图 |
| 04 | L4 | 核心模块与类关系 |
| 05 | L4 | API 与接口设计 |
| 06 | L4 | 配置与数据流 |
| 07 | L4 | 状态机与并发 |
| README | 索引 | 总索引 + 学习路径 + 主链路速览 |

## 串行处理顺序与验收

- 刷新顺序：00 → 01 → 02 → 03 → 04 → 05 → 06 → 07 → README。
- 每篇验收：`python3 docs/sourceReader/.progress/sr_tools.py verify docs/sourceReader/<篇>.md`，失效路径 = 0。
- 全库终验：`python3 docs/sourceReader/.progress/sr_tools.py verify docs/sourceReader/*.md`。
- 符号级校验：`codegraph_explore` 抽查核心符号定义行与文档 `+N` 一致。

## 变更记录

- 2026-11-18：本规范固化；sr_tools.py、anchor_rs.py 建立。全库记法升级为「符号 + 偏移」：126 处唯一 `file.rs +N` 全部转成 `file.rs · Symbol+N`（去重后 161 处正文/索引引用），55 处裸 `（+N）` 续引用按上下文解析为所属符号；0 处剩余绝对行号引用。`verify` 全库 + CodeGraph 符号级抽查 + 反向逐条回核（符号存在于文件、偏移落在函数体内）全部通过。
- 2026-11-18：全库 verify：145 处行号引用全部回核通过；0 失效路径；0 未解析；6 处「越界」经上下文消歧后全部命中正确文件。CodeGraph 抽查 reply/start_reply/turn/run_machine/create_state_machine/build_state_machine/step/run/ExtensionManager/AcpProviderConfig/ClientRequest/AcpProvider/SessionToolConfirmationState/ActiveTurnGuard 定义行全部与文档 `+N` 一致。覆盖审计：15/15 crate 至少被一篇引用。
