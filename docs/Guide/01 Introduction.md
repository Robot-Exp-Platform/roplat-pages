# 项目介绍

## Roplat 是什么

Roplat（**Ro**bot **Plat**form）是一个基于 Rust 的机器人操作平台。它的核心目标是：

> **把机器人系统中常见的运行时错误，前移到编译期解决。**

在传统的 ROS / ROS 2 开发中，你可能经历过这些痛苦：

- 消息类型写错，运行时才发现话题连不上
- 多线程回调导致不可复现的死锁
- Launch 文件改了一个参数，整个系统莫名挂掉
- 调试一个时序 bug 花了三天，最后发现是两个节点的执行顺序不确定

**Roplat 用 Rust 的类型系统、过程宏和编译期分析，将这些问题在 `cargo build` 阶段全部拦截。**

## 三层核心抽象

Roplat 的整个设计围绕三个正交概念：

### Node — 计算单元

节点是最小的计算单元。它接收输入、产出输出，有明确的生命周期：

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

节点是**纯计算**——它不关心自己何时被调用、被谁调用、与谁连接。这些都由更上层的抽象管理。

### Rhythm — 时间驱动

节律源决定"什么时候执行"。它驱动一组节点按特定节奏运行：

```rust
pub trait Rhythm {
    type Yield: Send;    // 给节点的输入（如时间戳、传感器数据）
    type Feed;           // 节点的输出反馈

    fn drive<N, F, Fut>(&mut self, nodes: N, op_domain: F)
        -> impl Future<Output = Self::Output> + Send;
}
```

内置四种节律源：

| 节律源 | 用途 | 示例 |
|:------|:-----|:-----|
| `SysTimer` | 固定周期定时器 | 控制回路 100Hz |
| `CountRhythm` | 执行固定次数 | 初始化序列 |
| `EventRhythm` | 外部事件触发 | 传感器帧到达 |
| `Iterator` 适配器 | 数据驱动 | 离线回放 / 批处理 |

### System — 编排容器

系统用声明式 DSL 描述节点之间的连接关系，编译期自动生成调度代码：

```rust
#[roplat::system]
async fn main() {
    let mut source = SensorNode::new();
    let mut filter = KalmanFilter::new();
    let mut ctrl   = PIDController::new();
    let mut motor  = MotorDriver::new();

    timer_100hz >> {
        source >> filter >> ctrl >> motor;
    };
}
```

`>>` 表达数据流方向，作用域 `{}` 表达并发边界。**代码即拓扑图**——你看到的代码结构就是系统的执行结构。

## 编译期做了什么

当你写下 `#[roplat::system]` 并编译时，Roplat 的过程宏会：

1. **解析 DSL** — 将 `>>` 操作符和作用域转换为有向图（FlowGraph）
2. **图规约** — 应用 R0-R4 五条规则，将复杂拓扑规约为最优调度序列
3. **死锁检测** — 分析跨节律域的通道依赖，发现环路立即报错
4. **代码生成** — 产出完全展开的 `async` Rust 代码，无运行时调度开销
5. **类型检查** — Rust 编译器接手，验证所有节点连接的类型匹配

最终产物是**零开销的静态调度代码**——没有动态分发、没有 vtable、没有运行时反射。

## 多语言支持

Roplat 不要求所有节点都用 Rust 写。通过 `#[roplat::node]` 宏的傀儡模式，你可以声明 C++ 或 Python 实现的节点：

```rust
#[roplat::node(lang = "cpp", input(data, SensorData), output(cmd, MotorCommand))]
pub struct CppController { pub gain: f64 }

#[roplat::node(lang = "py", input(image, CameraFrame), output(det, Detection))]
pub struct PyDetector { pub threshold: f64 }
```

构建系统会自动生成：

- C++ 头文件和 FFI 桥接代码
- Python ctypes 绑定和基类
- 消息类型的跨语言定义

三种语言的节点在同一个 `system!` 中无缝连接，类型安全由编译器保证。

## 通讯模型

节点间的数据传递有两条路径：

**主流通讯**（Primary）：节点的 `Input → Output` 链路，由 `>>` 操作符在 system DSL 中声明，编译期确定。

**旁路通讯**（Sideband）：用于状态共享和跨域通信的并行通道：

| 原语 | 语义 | 适用场景 |
|:-----|:-----|:---------|
| 三缓冲（Triple Buffer） | 始终读最新值，写端无阻塞 | 传感器状态、位姿同步 |
| 环形队列（Ring Buffer） | FIFO 有序，无锁 SPSC | 命令序列、事件日志 |

两种原语都是 **lock-free** 实现，跨 Rust / C++ / Python 语言边界透明可用。

## 项目结构

```text
roplat/               # 核心运行时（Node, Rhythm, Comm, TypeBinding）
roplat_macros/         # 过程宏（system!, node!, roplat_msg!）
roplat_build/          # 构建期代码生成（C++ 头文件、Python 存根）
roplat_launch/         # YAML 启动系统（ArchConfig, ParamConfig）
roplat_cpp/            # C++ 封装层
roplat_py/             # Python 封装层
cargo-roplat/          # CLI 工具（generate, run, topology）
```

## 下一步

- **想动手写代码？** → [快速开始](../QuickStart/00%20快速开始总览.md)
- **想深入理解概念？** → [Node 节点](../Concepts/01%20Node.md)
- **想参与开发？** → [项目入门](../Controbuction/0%20项目入门.md)
