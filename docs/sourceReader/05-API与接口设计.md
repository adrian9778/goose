# 05 · API 与接口设计

> 层级：L4 源码补齐 · 本文覆盖对外与对内契约：ACP 协议（server 端 + client 端 provider）、`Provider` trait、`ProviderDef` 定义层、`ExtensionConfig` 契约。

## 一句话定位

goose 的接口分两类：
- **对外（ACP）**：goose 作为 ACP **agent** 对外服务（`goose acp` / `goose serve` / Desktop），以及作为 ACP **client** 把别的 agent 当 provider（`AcpProvider`，供 `codex-acp`/`claude-acp`/`amp-acp`/`copilot-acp`/`pi-acp` 复用）。
- **对内**：`Provider` trait（provider 实现契约）、`ProviderDef`（定义层，构造 provider）、`ExtensionConfig`（扩展配置契约）。

## ACP Agent Server 契约

goose 实现 `agent_client_protocol::Handler<Client>`，`AcpConnectionHandler`（server.rs · AcpConnectionHandler+0）是每个 ACP 连接的处理者。`AcpConnection` 持有该连接对应的 `StateMachineServices`（共享），按 session 管理运行态。

### 入口与传输

| 传输 | 命令 / 路径 | 装配 |
|---|---|---|
| stdio | `goose acp` → `acp::server::run`（server.rs · run+0） | `AcpServer::new` → `create_connection` → `serve`（SacpAgent over ByteStreams） |
| HTTP+WS | `goose serve`（feature acp-http） | `LazyAcpConnection`（server.rs · LazyAcpConnection+0）按连接建 `AcpConnection` |

`serve`（server.rs · serve+0）把 read/write 包成 `SacpAgent.builder().with_handler(handler).connect_to(ByteStreams)`。

### 方法契约（agent 端实现）

| 方法 | Handler | 说明 |
|---|---|---|
| `initialize` | 协议自动 | 返回 capabilities（`agent_capabilities_meta`，server.rs · agent_capabilities_meta+0） |
| `session/list` | `handle_list_sessions` | 列出会话 |
| `session/new` | `handle_new_session` | 建会话 |
| `session/load` | `on_load_session`（`on_load_session+0`）→ `handle_load_session` | 载入会话 |
| `session/close` | `handle_close_session` | 关闭会话 |
| `session/update` | `handle_update_session` | 更新会话（标题/配置） |
| `prompt` | `on_prompt`（`on_prompt+0`）→ `handle_prompt` | 主推理入口 |
| `tool/notifications` | `handle_tool_*`（`handle_tool_request+0`/`handle_tool_response+0`） | 工具调用通知 |
| `request_permission` | `handle_tool_permission_request`（`handle_tool_permission_request+0`） | 审批请求 |
| 自定义（goose 扩展） | `custom_dispatch.rs` 等 | recipe 参数、device code、session 通知等 unstable 方法 |

### `prompt` 处理要点（server.rs · on_prompt+0）

- ACP session_id = 本地 session 的 thread id（`on_prompt+5`）。
- 生成 `run_id` + `cancel_token`，`start_active_run` 注册活动 run（`on_prompt+12`）。
- `ActiveRunDropGuard`：prompt future 被 drop（roaming 连接断）时释放 run（`on_prompt+18`）。
- `send_active_run_update` 通知 client 当前 run（`on_prompt+31`）。
- 调 `services.reply(...)` 流式回传，`chain_tracker` 聚合 chain 摘要（`forward_agent_stream+145`）。

### 客户端能力协商（server.rs · ClientCapabilitiesMeta+0）

`ClientCapabilitiesMeta` 解析 client 的 `meta.goose`：`mcpHostCapabilities`、`customNotifications`、`recipeParameterRequests`、`toolCallLabelEnrichment`。这些决定 goose 是否发对应的自定义通知/请求。

## ACP Provider（把 ACP agent 当 provider）

`AcpProvider`（acp/provider.rs）实现 `Provider` trait，内部起一个 ACP **client** 进程（如 `codex`、`claude`、`amp`），把 goose 的 `provider.stream` 翻译成 ACP `prompt` 请求。

### 契约与配置

`AcpProviderConfig`（provider.rs · AcpProviderConfig+0）：
- `command` / `args` / `env` / `env_remove`：起子进程；
- `work_dir`：工作目录；
- `mcp_servers: Vec<McpServer>`：传给 ACP 的 MCP server；
- `session_mode_id` / `session_config_options`：会话模式/配置选项；
- `model_config_option_id`：模型选择 option；
- `mode_mapping: HashMap<GooseMode, Vec<String>>`：GooseMode → ACP mode；
- `notification_callback`：会话通知回调。

`extension_configs_to_mcp_servers`（provider.rs · extension_configs_to_mcp_servers+0）：把 `ExtensionConfig`（Stdio/StreamableHttp）转成 ACP `McpServer`；socket-backed HTTP 与 Platform 扩展被跳过（`+1867/+1912`）。

### 关键行为

- `ACP_CURRENT_MODEL = "current"`（provider.rs · ACP_CURRENT_MODEL+0）：占位，`connect()` 时解析成实际模型。
- `stream`（provider.rs · stream+0）：`apply_model_if_changed` + `apply_effort_if_changed` → `messages_to_prompt` → `prompt(session_id, blocks)` → 收 `mpsc::Receiver<AcpUpdate>` 流。
- `ClientRequest` 枚举（provider.rs · ClientRequest+0）：`NewSession` / `LoadSession` / `CloseSession` / `SetMode` / `SetConfigOption` / `Prompt` 等，经内部 channel `self.tx` 发给 ACP client 循环。

## Provider trait（provider 实现契约）

`Provider`（provider-types/src/base.rs · Provider+0）是所有 provider 的**运行时契约**。核心：

```rust
fn get_name(&self) -> &str;                              // 必实现
async fn stream(&self, model_config, system, messages, tools)
    -> Result<MessageStream, ProviderError>;             // 必实现（流式）
async fn complete(&self, ...) -> Result<(Message, ProviderUsage), ProviderError>;  // 默认：collect_stream
```

其它有默认实现的钩子：

| 方法 | 默认 | 说明 |
|---|---|---|
| `provider_session_id` | None | 远端会话 id |
| `resume(session_id)` | Ok(()) | 恢复远端会话 |
| `get_context_limit` | ContextLimitResolver | 模型上下文限制 |
| `retry_config` | default | 重试配置 |
| `fetch_supported_models` / `_model_info` | 空 | 模型清单 |
| `fetch_recommended_models` | 过滤 canonical | 推荐模型 |
| `map_to_canonical_model` | 查 canonical | 模型映射 |
| `manages_own_context` | false | 是否自己管理 context（CLI wrapper 为 true） |
| `supports_builtin_tools` | `!manages_own_context` | 是否用内置工具 |
| `configure_oauth` | Err | OAuth 配置 |
| `refresh_credentials` | Err | 凭据刷新 |

`MessageStream`（provider-types/src/base.rs · MessageStream+0）= `Pin<Box<dyn Stream<Item=Result<(Option<Message>, Option<ProviderUsage>), ProviderError>>>>`。

`ProviderError`（errors.rs · ProviderError+0）枚举：`NotConfigured` / `Authentication` / `ContextLengthExceeded` / `RateLimitExceeded{retry_delay}` / `ServerError` / `NetworkError` / `RequestFailed` / `InvalidValue` / `ExecutionError` / `UsageError` / `NotImplemented` / `EndpointNotFound` / `CreditsExhausted{top_up_url}` / `Refusal`。

## ProviderDef（定义层）

`ProviderDef`（goose/src/providers/base.rs · ProviderDef+0）是 `goose` crate 里把「provider 名称 → 实现」的**构造契约**，区别于运行时 `Provider` trait：

```rust
pub trait ProviderDef: ProviderDescriptor + Send + Sync {
    type Provider: Provider + 'static;
    const SESSION_BOUND: bool = false;        // 是否会话绑定（不能共享）
    const RUNS_OWN_TOOL_LOOP: bool = false;   // 是否自跑工具循环（不启动 MCP server）
    fn from_env(extensions, tls_config) -> BoxFuture<Result<Self::Provider>>;
    // 默认委托 from_env：
    fn from_env_with_working_dir(...) -> ...
    fn from_env_with_default_model(...) -> ...
}
```

`ProviderDescriptor`（provider-types/src/base.rs · ProviderDescriptor+0）声明元数据：`fn metadata() -> ProviderMetadata`（名称、描述、默认模型、配置键、setup steps、capabilities）。

### 实现类型（`goose/src/providers/*_def.rs`）

| 实现 | Provider 类型 | 说明 |
|---|---|---|
| `AnthropicProviderDef`（anthropic_def.rs · AnthropicProviderDef+0） | `AnthropicProvider` | Claude |
| `AzureProvider`（azure.rs · AzureProvider+0） | `OpenAiCompatibleProvider` | Azure OpenAI |
| `AzureFoundryProviderDef`（azure_foundry_def.rs · AzureFoundryProviderDef+0） | `AzureFoundryProvider` | Azure Foundry |
| `AvianProvider`（avian.rs · AvianProvider+0） | `OpenAiCompatibleProvider` | Avian |
| `OpenAiProviderDef` / `OpenRouterProviderDef` | `OpenAiProvider` | OpenAI / OpenRouter |
| `OllamaDef` | `OllamaProvider` | 本地/云 Ollama |
| `DatabricksV2ProviderDef` | `DatabricksV2Provider` | Databricks |
| `BedrockProvider`（bedrock.rs · BedrockProvider+0） | `Self` | AWS Bedrock |
| `GoogleProviderDef` | `GoogleProvider` | Gemini |
| `AmpAcpProvider`（amp_acp.rs · AmpAcpProvider+0） | `AcpProvider` | SESSION_BOUND+RUNS_OWN_TOOL_LOOP=true |
| `CodexAcpProvider` / `ClaudeAcpProvider` / `CopilotAcpProvider` / `PiAcpProvider` | `AcpProvider` | 各 ACP 客户端 |
| `LocalInferenceProvider` | 本地 | llama-cpp/mlx |
| `TestProvider`（testprovider.rs · TestProvider+0） | `Self` | 测试录制/回放 |

## ExtensionConfig 契约

`ExtensionConfig`（goose/src/agents/extension.rs · ExtensionConfig+0）四种变体（见 L4a），字段契约要点：

| 变体 | 关键字段 | 说明 |
|---|---|---|
| `Stdio` | name, cmd, args, envs, env_keys, timeout, cwd, bundled | 子进程 MCP |
| `Builtin` | name, display_name, timeout | bundled MCP |
| `Platform` | name, display_name | 进程内扩展 |
| `StreamableHttp` | uri, headers, envs, socket, client_id, client_secret_key, scopes, timeout | HTTP/UDS MCP |

- `env_keys`：从环境变量 / keyring secret 注入的键（`merge_environments`，extension.rs · merge_environments+0）。
- `Envs` 过滤 `DISALLOWED_KEYS`（如 `LD_PRELOAD`，extension.rs · is_disallowed+0）。
- `available_tools`：预声明工具名。
- `config.key()`：去重键。
- `ExtensionConfig::resolve(config)`（extension.rs · substitute_env_vars+0）：环境变量替换、secret 解析。

## 依赖版本

- `agent-client-protocol` / `-schema` / `-http`（Cargo.toml workspace）：ACP 协议实现，`agent-client-protocol = 2.2.0`。
- `rmcp`：MCP 协议（3.4.1，schemars feature）。

## 源码索引（绝对行号）

- `crates/goose/src/acp/server.rs`：`AcpConnectionHandler` +0 / `serve` +0 / `run` +0 / `on_prompt` +0 / `on_load_session` +0 / `handle_tool_request` +0 / `handle_tool_response` +0 / `handle_tool_permission_request` +0 / `agent_capabilities_meta` +0 / `ClientCapabilitiesMeta` +0 / `LazyAcpConnection` +0
- `crates/goose/src/acp/provider.rs`：`AcpProviderConfig` +0 / `ClientRequest` +0 / `ACP_CURRENT_MODEL` +0 / `stream` +0 / `extension_configs_to_mcp_servers` +0 / `filter_supported_servers` +0 / `messages_to_prompt` +0
- `crates/goose/src/providers/base.rs`：`ProviderType` +0 / `ProviderDef` +0
- `crates/goose/src/providers/anthropic_def.rs`：`AnthropicProviderDef` +0 / `from_env` +0
- `crates/goose/src/providers/azure.rs`：`AzureProvider` +0 / `is_v1_endpoint` +0
- `crates/goose/src/providers/azure_foundry_def.rs`：`AzureFoundryProviderDef` +0
- `crates/goose/src/providers/avian.rs`：`AvianProvider` +0
- `crates/goose/src/providers/bedrock.rs`：`BedrockProvider` +0 / `ConverseRequestParts` +0
- `crates/goose/src/providers/amp_acp.rs`：`AmpAcpProvider` +0
- `crates/goose-provider-types/src/base.rs`：`ProviderDescriptor` +0 / `MessageStream` +0 / `Provider` +0 / `collect_stream` +0
- `crates/goose-provider-types/src/errors.rs`：`ProviderError` +0
- `crates/goose/src/agents/extension.rs`：`ExtensionConfig` +0 / `merge_environments` +0 / `Envs::is_disallowed` +0 / `substitute_env_vars` +0