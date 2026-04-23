# 2026-04-24 IPC 后续硬化：连接选项 / 背压水位 / e2e 测试

## 背景

MVP 跨进程链路跑通后，暴露三个工程性短板：

1. **订阅者必须手写 `NotReady` 重试循环**：每个调用方都复制一份 `loop + sleep + match IpcError::NotReady`，既啰嗦又易错
2. **TCP 后端 outbox 近似无界**：若订阅者卡死，发布者内存会无限增长，无法用于长期驻留的机器人场景
3. **跨进程验证依赖手工 PowerShell 脚本**：没进 `cargo test`，回归靠人盯

本轮把这三项补齐。

## 设计决策

### 1. `ConnectOptions` / `IpcOptions`

在 `comm::ipc::ring_buffer` 新增两个选项结构体：

```rust
pub struct ConnectOptions {
    pub connect_timeout: Option<Duration>,  // None = 无限等待
    pub retry_interval: Duration,
}

pub struct IpcOptions {
    pub connect: ConnectOptions,
    pub tcp: TcpOptions,
}
```

预设三个构造器：`ConnectOptions::non_blocking()` / `wait_forever()` / `with_timeout(d)`。默认 30 秒超时、500ms 间隔 —— 覆盖 CI 与本地调试常见场景。

工厂函数新增 `create_ipc_ring_buffer_with_opts`，在订阅侧内部吸收 `IpcError::NotReady` / `IpcError::Io(_)`，直到超时或成功。`create_ipc_ring_buffer` 保留为薄包装（使用默认选项），源兼容。

**为什么把重试放在工厂而不是 Reader 内部**：连接阶段是一次性动作，握手完成后状态机就是单向的（`Ready → PeerGone → end`），没必要把重连写进 hot loop。未来若要做透明断线重连（Reader 自行 re-dial），那是独立状态机，不和本层冲突。

### 2. TCP 背压水位

在 `TcpTransport` 存储 `TcpOptions { high_watermark: Option<usize>, overflow: OverflowPolicy }`，`publish()` 遍历每个 peer outbox 时检查水位：

```rust
enum OverflowPolicy {
    DropOldest,   // 默认：丢队首最旧一帧，保留最新
    DropNewest,   // 丢当前新帧（对端暂时反压时的温和策略）
    Error,        // 返回 IpcError::Protocol（供故障注入测试）
}
```

**为什么默认 `DropOldest`**：机器人场景消息通常有时效性（姿态、传感器读数），最新数据价值远大于历史数据。真·可靠传输应显式改用消息队列服务（Kafka / NATS），不应由本地 IPC 承担。

**水位独立作用于每个 peer**：多订阅者场景下，慢订阅者不应拖垮快订阅者。每个 peer outbox 独立判定，符合「失败隔离」原则。

### 3. 跨进程集成测试

`examples/ipc_pubsub/tests/cross_process.rs` 通过 `env!("CARGO_BIN_EXE_publisher")` 取得由 Cargo 编译产物路径，`std::process::Command::spawn` 起子进程。关键约束：

- **隔离运行时目录**：每次测试 mint 一个 `$TEMP/roplat-ipc-test-<pid>-<nanos>/`，测试结束清理。避免与用户本地正在运行的 IPC 端点碰撞
- **发布者 / 订阅者自行退出**：两个 bin 读取环境变量 `IPC_PUBSUB_MAX_SEQ` / `IPC_PUBSUB_MAX_MSGS`，集成测试里分别设为 200 / 5。无需测试框架 kill
- **时间上限保底**：订阅者 15 秒内未退出即视为挂死，强杀并 fail

验证：`cargo test -p ipc_pubsub --test cross_process -- --nocapture` 在 1.12s 内通过。

## 验证结果

```
$ cargo check --workspace
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 11.42s

$ cargo test -p roplat --lib comm::ipc --
test result: ok. 7 passed; 0 failed

$ cargo test -p ipc_pubsub --test cross_process --
running 1 test
test pubsub_end_to_end ... ok
test result: ok. 1 passed; 0 failed; finished in 1.12s
```

## 示例切换

`examples/ipc_pubsub` 的两个 bin 同步换用新 API：

- 发布者：`TcpOptions { high_watermark: Some(256), overflow: DropOldest }`
- 订阅者：`ConnectOptions::wait_forever()`，代码从 15 行重试循环缩成 5 行选项构造

两个 bin 新增 `IPC_PUBSUB_MAX_SEQ` / `IPC_PUBSUB_MAX_MSGS` 环境变量，为集成测试与 CI 准备了自退出钩子。

## 涉及文件增量

- 修改：[roplat/src/comm/ipc/ring_buffer.rs](../../../roplat/roplat/src/comm/ipc/ring_buffer.rs)（新增 `ConnectOptions` / `IpcOptions` / `TcpOptions` / `OverflowPolicy` 与 `create_ipc_ring_buffer_with_opts`，内含 `ConnectSubscriber` trait 解耦重试与后端）
- 修改：[roplat/src/comm/ipc/backend/tcp.rs](../../../roplat/roplat/src/comm/ipc/backend/tcp.rs)（`bind_publisher_with_opts` + `publish()` 背压分支）
- 修改：[roplat/src/comm/ipc/mod.rs](../../../roplat/roplat/src/comm/ipc/mod.rs)（新类型 re-export）
- 修改：[roplat/src/comm/mod.rs](../../../roplat/roplat/src/comm/mod.rs)（顶层 re-export）
- 修改：[examples/ipc_pubsub/src/publisher.rs](../../../roplat/examples/ipc_pubsub/src/publisher.rs)（使用 `TcpOptions` 背压 + `IPC_PUBSUB_MAX_SEQ`）
- 修改：[examples/ipc_pubsub/src/subscriber.rs](../../../roplat/examples/ipc_pubsub/src/subscriber.rs)（使用 `ConnectOptions::wait_forever()` + `IPC_PUBSUB_MAX_MSGS`）
- 新增：[examples/ipc_pubsub/tests/cross_process.rs](../../../roplat/examples/ipc_pubsub/tests/cross_process.rs)（隔离 runtime dir 的 e2e）
- 修改：[roplat/TODO.md](../../../roplat/TODO.md)（勾掉三项）

## 剩余工作

- UDS / Windows Named Pipe 后端（本地 ~10μs 延迟）
- 共享内存后端 + `IpcTripleBuffer<T>`（零拷贝，μs 级）
- `#[system]` 宏识别 IPC 端点边（自动生成 rendezvous 配置）
- IPC 消息参与 `#[replay]` 录制
- `cargo roplat ipc ls` / `ipc introspect` CLI
