# 项目介绍

Roplat 是一个面向机器人应用的 Rust 框架。它的目标不是复制 ROS 2 的运行时发现模型，而是提供一种更静态、更可检查、更适合实验复现和控制链路的组织方式。

一句话概括：

> 用普通 Rust 类型写节点，用 Rhythm 表达执行节奏，用 `#[roplat::system]` 把节点编译成确定的数据流图。

## Roplat 解决什么问题

机器人系统里常见的问题往往不是“单个函数写错了”，而是系统边界出了问题：

- 节点 A 的输出类型和节点 B 的输入类型不一致。
- 一个周期任务被手写成散落在多个文件里的循环和 `tokio::spawn`。
- C++、Python、Rust 节点之间的消息布局靠手工约定维护。
- 拓扑写在 launch 文件、回调和全局状态里，人脑很难确认真实执行图。
- 真机实验时才发现某条通道没有连接、某个进程 schema 不匹配、某个节点执行顺序不稳定。

Roplat 的思路是把这些关系尽量提前到代码和构建阶段表达：

- 数据流拓扑写在 `#[roplat::system]` 里。
- 周期、事件、计数、迭代、回放由 Rhythm 负责。
- 节点只表达一次计算，不自己管理调度。
- 消息类型由 Rust 结构体驱动，生成 C++ 头文件和 Python stub。
- C++ / Python 节点由 Rust puppet 声明，`roplat_build` 生成桥接文件。

## 适合的场景

Roplat 特别适合这些项目：

- 机器人控制链路：传感器、滤波、控制器、驱动输出之间有固定拓扑。
- 多语言实验系统：核心框架用 Rust，已有算法在 C++ 或 Python 中。
- 可复现实验：需要计数节律、迭代节律、录制回放或明确的拓扑图。
- 进程内高确定性、进程间可组合的系统：单进程内部静态编排，跨进程用 IPC。
- 下游驱动库和 benchmark：希望把节点、节律、通信方式都写成可检查的工程结构。

它不适合把所有东西都运行时动态注册、动态发现、动态重连的应用模型。Roplat 可以和外部系统协作，但它的强项是“代码里已知的图，构建时尽量检查”。

## 三个核心抽象

### Node：一次计算

`Node` 是最小计算单元。它只关心输入和输出：

```rust
pub trait Node: Send + Sync {
    type Input;
    type Output;
    type Error;

    async fn process(&mut self, input: Self::Input) -> Self::Output;
    async fn on_init(&mut self) -> Result<(), Self::Error> { Ok(()) }
    async fn on_shutdown(&mut self) -> Result<(), Self::Error> { Ok(()) }
}
```

一个节点不应该自己决定“每 10ms 跑一次”。它只实现“给我一次输入，我产出一次输出”。

### Rhythm：什么时候运行

`Rhythm` 负责执行节奏。内置常用节律包括：

| 节律 | 用途 |
|---|---|
| `SysTimer` | 固定周期控制、采样、状态同步 |
| `CountRhythm` | 测试、示例、有限步仿真 |
| `EventRhythm<T>` | 外部事件触发 |
| Iterator rhythm | 数据集、轨迹、离线输入 |
| Replay rhythm | 确定性录制与回放 |

当你想写 `loop { ... }` 时，先问：这个循环是不是一个 Rhythm？

### System：谁连接谁

`#[roplat::system]` 是拓扑入口。你用 `>>` 描述数据流：

```rust
#[roplat::system]
async fn main() {
    let mut source = Source::default();
    let mut filter = Filter::new();
    let mut sink = Sink;
    let (_, mut timer) = roplat::rhythm::create_count_rhythm(3);

    timer >> {
        source >> filter >> sink;
    };
}
```

这段代码表达的是：

1. `timer` 拥有这个执行域。
2. `source` 的输出进入 `filter`。
3. `filter` 的输出进入 `sink`。
4. 最后的分号表示本轮不向 Rhythm 反馈额外状态。

## 多语言不是附加脚本

Roplat 的多语言不是“Rust 运行时去找一些 Python 脚本”。推荐流程是：

1. 在 Rust 中定义消息。
2. 在 Rust 中声明 C++ / Python puppet 节点。
3. 通过 `build.rs` 调用 `roplat_build`。
4. 构建时生成 C++ / Python 基类、用户文件、FFI 桥接和 stub。
5. 在 System DSL 中像普通节点一样连接它们。

Python 运行时支持位于 `roplat_py`，不会强制污染纯 Rust 下游 crate。

## 项目组成

| crate | 面向下游的作用 |
|---|---|
| `roplat` | 核心 API、宏重导出、Node、Rhythm、通信、错误类型 |
| `roplat_build` | `build.rs` 里的多语言代码生成和 native build |
| `roplat_cpp` / `roplat_cpp_msg` | C++ 节点和透明消息支持 |
| `roplat_py` | Python 节点运行时桥接和 PyO3 依赖 |
| `roplat_launch` | YAML 架构和参数模型 |
| `cargo-roplat` | generate、run、topology、expand、IPC 诊断等 CLI |

## 下一步

- 想立刻跑通项目：读 [快速开始总览](../QuickStart/00%20快速开始总览.md)。
- 想先理解抽象：读 [概念导读](../Concepts/00%20概念导读.md)。
- 想知道为什么这样设计：读 [设计哲学](02%20Design.md)。
