# 通讯模型

Roplat 的通信分为两类：主流数据流和旁路通信。

## 主流数据流

主流数据流是 System DSL 中的节点边：

```rust
timer >> {
    sensor >> filter >> controller;
};
```

这是普通 roplat 应用的默认通信方式。它的特点：

- 在编译期可见。
- 参与拓扑和调度分析。
- 类型由 Rust 编译器检查。
- 用户不需要手动持有底层通道。

只要值是在同一个系统图中从一个节点传给另一个节点，就优先使用主流数据流。

## 旁路通信

旁路通信用于不适合放进普通 System DSL 边的情况：

| 原语 | 语义 | 适合 |
|---|---|---|
| Triple Buffer | 最新值，多读者 | 状态、位姿、传感器快照 |
| Ring Buffer | FIFO 事件流 | 命令、日志、任务队列 |
| Opaque Data | 跨语言未知结构 | Python/C++ native object |
| IPC | 跨进程通信 | 发布/订阅、进程边界 |

判断方法：

1. 是普通节点到节点吗？用 `>>`。
2. 是跨节律域共享最新状态吗？用 triple buffer。
3. 是必须保留顺序的事件流吗？用 ring buffer。
4. 是跨进程吗？用 IPC。
5. 是语言 native 对象吗？用 opaque。

## Triple Buffer

Triple buffer 表达“我只关心最新值”。

```rust
let (publisher, subscribers) = roplat::comm::create_triple_buffer::<State>(2);
```

写端发布最新状态，多个读端读取快照。适合 robot state、pose、diagnostics 等。

## Ring Buffer

Ring buffer 表达“事件不能被最新值覆盖”。

```rust
let (writer, reader) = roplat::comm::create_ring_buffer::<Command>(128);
```

适合命令序列、离散事件、任务输入。

## IPC

IPC 是跨进程版本的旁路通信。它包含：

- endpoint URI。
- schema id 和 message version。
- rendezvous 文件发现。
- loopback/TCP 后端。
- ring/triple buffer 语义。

IPC payload 推荐使用：

```rust
#[roplat::roplat_msg(version = 1)]
#[repr(C)]
#[derive(Copy, Clone, Debug)]
pub struct Pose {
    pub seq: u64,
    pub x: f32,
    pub y: f32,
    pub z: f32,
}
```

这样发布端和订阅端可以在握手阶段检查 schema。

## 诊断命令

```powershell
cargo roplat ipc ls
cargo roplat ipc ls --json
cargo roplat ipc introspect "roplat-ipc://<namespace>/<name>?msg=<schema>&v=<version>"
```

## 不要混淆两类通信

不要为了“可扩展”把系统图里所有边都写成 ring buffer 或 IPC。这样会让 roplat 宏看不见拓扑，也失去编译期检查能力。
