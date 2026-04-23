# 2026-04-24 IPC 补完：三缓冲语义 + CLI 诊断

## 背景

在 `ConnectOptions` / `TcpOptions` / e2e 集成测试落地后，IPC 分支仍缺两块「能独立闭环且不引入新平台依赖」的工作：

1. **跨进程三缓冲语义**：之前只有 `IpcRingBuffer`（FIFO 无损），缺与进程内 `triple_buffer` 对应的「最新值覆盖」语义
2. **运维可见性**：rendezvous 目录一直是文件系统隐形存在，出问题只能 `ls /tmp/roplat/ipc/**` 手工 cat

本轮补上这两项。UDS / Named Pipe 后端延后到下一次有跨平台 stream I/O 抽象时一次性落地；真·共享内存后端需要专门设计跨进程 ctrl block，亦独立推进。

## 设计决策

### 1. `IpcTripleBuffer<T>` 基于 TCP 广播的语义 facade

新增 `comm::ipc::triple_buffer` 模块，`IpcTripleWriter<T>` / `IpcTripleReader<T>` 直接复用 `create_ipc_ring_buffer_with_opts` 建立的 transport 栈。区别仅在读端：

```rust
pub fn get_latest(&self) -> IpcResult<Option<T>> {
    // 抽干 inbox，只留最后一帧
    let mut last_bytes = None;
    while let Some(b) = self.transport.try_recv()? { last_bytes = Some(b); }
    // 更新缓存，返回缓存副本（对齐 Subscriber::get_latest 语义）
}
```

**为什么不做真正的三缓冲 ctrl 块**：跨进程真·三缓冲需要共享内存 + 跨进程原子 ready 指针。当前 MVP 在应用层以「写端广播所有帧 + 读端抽干保留最新」模拟有损覆盖语义，功能等价但延迟受限于 TCP 搬运。后续引入 shm 后端时再做零拷贝升级。

**对应用方的契约**：写端 `publish(&T)` 永不阻塞；读端 `get_latest()` 返回 `Option<T>`，无新帧时继续返回上一帧缓存 —— 与 `comm::triple_buffer::Subscriber::get_latest` 一致，不暴露 FIFO 细节。

工厂函数复用 `ring_buffer` 的：

```rust
pub fn create_ipc_triple_buffer<T: Copy>(...)
    -> IpcResult<(Option<IpcTripleWriter<T>>, Option<IpcTripleReader<T>>)>
pub fn create_ipc_triple_buffer_with_opts<T: Copy>(..., opts: &IpcOptions) -> ...
```

### 2. `cargo roplat ipc ls` / `ipc introspect`

诊断子命令读取 rendezvous 目录。实现拆分：

- **library 侧**：在 `comm::ipc::rendezvous` 新增 `RendezvousDir::scan_all() -> Vec<(RendezvousDescriptor, alive: bool)>`，递归遍历 `$ROPLAT_RUNTIME_DIR/ipc/**/*.rdv`。不校验 schema（诊断路径恰恰需要看到错配），不主动清理僵尸。
- **CLI 侧**：`cargo-roplat` 新增 `Ipc { cmd: IpcCmd }` 枚举分支 → `Ls { root, json }` / `Introspect { uri, root }`。
- **输出**：`ls` 默认人类可读表格（`URI / BACKEND / ADDRESS / SCHEMA_ID / PID / ALIVE`），`--json` 切换机器可读。`introspect` 按字段逐行输出，并在 URI 与 rendezvous 的 `schema_id` / `msg_version` 错配时显式警告。

**为什么把 scan 放在 library**：将来 `#[system]` 宏和可视化工具都会复用此接口，不应把解析逻辑锁死在 CLI。

CLI 依赖：`cargo-roplat` 新增 `roplat` 为 path 依赖、`serde` 开启 `derive` feature 以支持 JSON 输出。

## 验证

```
$ cargo check --workspace
  ✅ 工作区内所有包通过

$ cargo test -p roplat --lib comm::ipc --
  ✅ 8 passed (新增 triple_buffer::tests::loopback_latest_wins)

$ cargo test -p ipc_pubsub --test cross_process --
  ✅ 1 passed (pubsub_end_to_end, 回归)

$ cargo run -p cargo-roplat -- roplat ipc ls
  ✅ 列出当前 runtime dir 下的端点，正确检测到手动测试遗留的 DEAD 僵尸项
```

CLI 意外地成了僵尸 rendezvous 检查器：`cargo roplat ipc ls` 看到 `ALIVE = DEAD` 即可手动 `rm` 清理（自动清理交给订阅者 lookup 路径）。

## 涉及文件增量

- 新增：[roplat/src/comm/ipc/triple_buffer.rs](../../../roplat/roplat/src/comm/ipc/triple_buffer.rs)
- 修改：[roplat/src/comm/ipc/mod.rs](../../../roplat/roplat/src/comm/ipc/mod.rs)（导出 triple_buffer 类型）
- 修改：[roplat/src/comm/ipc/rendezvous.rs](../../../roplat/roplat/src/comm/ipc/rendezvous.rs)（`scan_all()` + `check_pid_alive`）
- 修改：[roplat/src/comm/mod.rs](../../../roplat/roplat/src/comm/mod.rs)（顶层 re-export）
- 修改：[cargo-roplat/Cargo.toml](../../../roplat/cargo-roplat/Cargo.toml)（新增 `roplat` / `serde` derive feature）
- 修改：[cargo-roplat/src/main.rs](../../../roplat/cargo-roplat/src/main.rs)（`Ipc { Ls / Introspect }` 子命令 + `cmd_ipc`）
- 修改：[roplat/TODO.md](../../../roplat/TODO.md)（勾掉 2 项，剩 4 项）

## 剩余工作

- **UDS / Named Pipe 后端**：需先抽象一个跨 stream 类型（TCP/UDS/Pipe）的 reader/writer trait，再复用现有 accept/handshake 逻辑
- **真·共享内存后端**：shm ring ctrl block + 跨进程原子 ready 指针；μs 级延迟目标
- **`#[system]` 宏识别 IPC 端点边**：系统 DSL 层感知 IPC，自动生成 rendezvous 配置
- **IPC 参与 `#[replay]` 录制**：让 IPC 消息进入同一套确定性回放流
