# coverage-inventory — goose sourceReader 覆盖清单

一行一个能力/机制主题，标注代码证据、当前文档与处置。刷新基准：`main@71dd9a9aa`（== 当前 HEAD，0 提交漂移，2026-11-18）。

| 能力或机制 | 代码与测试证据 | 需求来源 | 当前文档 | 处置 | 状态 |
|---|---|---|---|---|---|
| 系统骨架（进程/组件/入口） | `crates/goose-cli/src/main.rs`、`crates/goose/src/agents/services.rs` | 可观察行为 | 01 | 无漂移，无需单列 | 完成 |
| 一次真实操作全路径 | `crates/goose-cli/src/session/mod.rs`（CliSession）、`services.rs`（reply） | 可观察行为 | 02 | 无漂移 | 完成 |
| 主链路逐跳（reply→turn→run_machine→step→infer→apply） | `services.rs`、`state_machine_builder.rs`、`machine.rs`、`inference.rs`、`session.rs` | 可观察行为 | 03 | 无漂移 | 完成 |
| 核心模块与类关系 | `goose-agent`（machine/operation/events/subagent）、`goose`（services/extension_manager/provider_manager/session） | 结构 | 04 | 无漂移 | 完成 |
| ACP 协议与 Provider 契约 | `crates/goose/src/acp/provider.rs`、`crates/goose/src/acp/server.rs`、`crates/goose/src/providers/*.rs`、`crates/goose-provider-types/src/base.rs` | 契约 | 05 | 无漂移 | 完成 |
| 配置与数据流 | `config/base.rs`、`config/providers.rs`、`config/declarative_providers.rs`、`config/paths.rs`、`recipe/`、`slash_commands/` | 结构+数据流 | 06 | 无漂移 | 完成 |
| 状态机与并发 | `machine.rs`（run/step）、`tool_confirmation_coordinator.rs`、`session_runtime.rs`、`events.rs`（Emitter）、`subagent_handler.rs` | 结构 | 07 | 无漂移 | 完成 |
| 15/15 crate 覆盖 | `crates/goose`、`goose-cli`、`goose-agent`、`goose-providers`、`goose-provider-types`、`goose-mcp`、`goose-sdk`、`goose-sdk-types`、`goose-context-management`、`goose-roaming`、`goose-local-inference`、`goose-acp-macros`、`goose-download-manager`、`goose-test`、`goose-test-support` | 结构 | 01/04/05 | 无需单列（已在 01 与相关 L4 篇覆盖） | 完成 |

## 审计结论（2026-11-18）

- **提交漂移：0**（`git rev-list --count 71dd9a9aa..HEAD` = 0；工作区仅 `docs/`、`.codegraph/` 未跟踪）。
- **行号引用：全部升级为「符号 + 偏移」**（161 处正文/索引 + 55 处裸续引用），反向逐条回核：符号存在于文件、偏移落在函数体内，全部通过。
- **符号级抽查（CodeGraph）**：`reply`@services.rs:813、`start_reply`@839、`turn`@1019、`run_machine`@1069、`create_state_machine`@723、`build_state_machine`@89、`step`@machine.rs:162、`run`@machine.rs:241、`ExtensionManager`@extension_manager/mod.rs:454、`AcpProviderConfig`@acp/provider.rs:61、`ClientRequest`@78、`AcpProvider`@274、`SessionToolConfirmationState`@tool_confirmation_coordinator.rs:17、`ActiveTurnGuard`@155 —— 全部与文档 `+N` 一致。
- **新增能力缺口：无**（0 提交漂移 ⇒ 无新入口/新能力/新配置需要补写）。
- **结构完整性**：围栏闭合、无占位（00 的 `TODO/TBD`、05 的 `...` 为规范条款与签名省略，属合法）、每篇先生产后开发、实质专题有生产图+开发图+三张表。

## 记法升级记录（2026-11-18）

- 全库绝对行号 → 符号+偏移：`file.rs +N` → `file.rs · Symbol+N`；`Symbol+0` = 定义行。
- 反算校验：每处 `file.rs · Symbol+N` 用 `anchor_rs.py` 还原，确认符号在该文件、偏移不越函数体。
- 唯一保留的裸 `+0` 在 00 规范篇（记法模板本身，合法）。

## 待验证事项

- 07 已标 `[待运行验证]`：LRU 驱逐与取消时序未实测（需运行期验证）。
