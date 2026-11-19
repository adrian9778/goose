# 00 · 文档规范与定位约定

> 本文档库为 goose（Rust AI Agent 框架 + Electron 桌面应用）的源码锚定阅读文档。
> 所有正文锚点遵守「符号 + 偏移」记法，源码以当前 `main` 分支 `71dd9a9aa` 为准。

## 定位

- **项目**：goose —— 用 Rust 实现的 AI Agent 框架，附带 CLI（`goose-cli`）、桌面应用（`ui/desktop`，Electron）、ACP（Agent Client Protocol）server。
- **工作区**：cargo workspace，`members = ["crates/*"]`，15 个 crate（见 `README.md` 的 crate 表）。
- **本文档库范围**：核心 agent 循环、状态机、会话管理、ACP 协议、Provider 体系、配置与数据流、扩展加载、并发模型。不逐行覆盖 Electron UI 组件与 testing crate 内部。

## 事实红线

1. **严禁编造**。所有接口、字段、默认值、调用链必须经 Grep/Read/实测查证。无法证实的显式标记：
   - `[源码未确认]` —— 仓库里找不到证据，但也不能断定没有；
   - `[源码未找到]` —— 已全量查过，确实不存在；
   - `[推断]` —— 有证据支撑的解释，不是原文写的；
   - `[待运行验证]` —— 需外部环境/运行期才能确认。
2. **禁止「同上 / 略 / 以此类推 / 省略号」替代核心内容**。
3. **冲突以代码为准**：README、注释、旧文档与实现不一致时，以源码与测试为准，并把差异写出来。
4. **实测数据标来源与日期**；只读查询，不写库。

## 锚点记法（正文引用统一用这套）

- 函数/方法/结构体/常量引用：`` `file.rs · Symbol+N` ``（`+0` = 符号定义行；目标行 − 定义行 = 偏移）。示例：`services.rs · reply+0`、`machine.rs · step+34`。
- 连续片段：`Symbol+0~+20`（同一符号内）；跨符号用 `SymbolA+0~SymbolB+0`。
- 非函数代码：`Struct：Node` / `Const：X` / `Module：rpc`。
- 调用关系标双方：`调用方文件 · 调用方+off ↓ 被调用方文件 · 被调用方`；`+off` 是该调用方符号内调用点行相对定义行的偏移。
- 目录前缀用于消歧：同名文件用 `crates/goose/src/agents/services.rs · reply+0`；无前缀时依赖上下文。
- 第三方依赖注明版本：`依赖：github.com/urfave/cli/v2`。
- **文末源码索引**给 `文件：Symbol +0`（符号 → 文件映射），不承诺行号稳定性。
- 记法由 `.progress/anchor_rs.py` 生成/校验：解析 `.rs` 顶层项与 impl 方法（brace 匹配 + 注释/字符串剥离），把 `文件+行号` 反算为 `Symbol+N`。

## 图

- 每篇 ≥1 张图：逻辑流/报文用 ASCII 图；架构用 Mermaid `flowchart`；调用用 `sequenceDiagram`；状态用 `stateDiagram-v2`；多表关系用 `erDiagram`。
- 每个 Mermaid 节点都要能映射回真实模块名/类名/函数名/文件路径。

## 成稿规范

- 正文用中文；源码路径、包名、类型、函数、API、配置键、命令、数据库字段、代码片段保留原文不翻译。
- 不许有占位：`TODO` / `TBD` / `FIXME` / 「待补充」/「同上」/「略」/ 省略号，一律不许出现在正文。
- 结构完整：文件非空；Markdown 层级与代码围栏闭合；Mermaid 块闭合且 ≥1 张图。
- 可复核：每条关键结论都能顺着锚点回到源码。
- 可重构：写清真实模块名/类名/函数名/文件路径 + 具体调用关系。

## 本文档库的状态机

每篇文档有固定生命周期：`pending → evidence_collected → outlined → drafted → verified → completed`，状态存于 `.progress/state.json` 与 `.progress/tasks.json`。跨轮只从磁盘恢复。