# 设计哲学

Roplat 的核心设计不是“多提供一套机器人 API”，而是重新划分机器人应用里最容易混乱的三个问题：

- 计算是什么？
- 什么时候运行？
- 谁连接谁？

这三个问题分别由 `Node`、`Rhythm`、`System` 处理。

## 运行期危险左移

机器人程序的失败成本很高。一个类型不匹配、调度顺序不稳定或消息 schema 错误，可能不是在单元测试里暴露，而是在真机运动中暴露。

Roplat 的第一原则是：

> 能在编译期或构建期发现的问题，不要留到运行期。

因此 Roplat 会尽量把下面这些关系显式化：

- 节点输入输出类型。
- 节点之间的数据流。
- 节律域边界。
- C++ / Python 节点端口。
- 透明消息的 C / Python 表示。
- IPC 消息的 schema 和版本。

这并不意味着运行期没有错误，而是意味着“系统结构错误”应尽可能早失败。

## 不手写调度循环

传统写法很容易从一个简单循环开始：

```rust
loop {
    let sensor = sensor.process(()).await;
    let command = controller.process(sensor).await;
    motor.process(command).await;
}
```

这段代码短期看起来直接，长期会把执行节奏、节点拓扑、错误恢复和生命周期混在一起。

Roplat 鼓励写成：

```rust
timer >> {
    sensor >> controller >> motor;
};
```

这样：

- Rhythm 拥有循环。
- System 拥有拓扑。
- Node 只拥有计算。
- 编译器和宏能看见图结构。

## 代码优先，而不是配置优先

Roplat 支持 YAML launch，但它的核心仍是代码优先。

推荐默认路径：

1. 先写 Rust 类型、节点和 `#[roplat::system]`。
2. 当系统需要外部架构文件、参数化启动或拓扑可视化时，再引入 launch。
3. 让 YAML 描述架构，不要把业务逻辑塞进 YAML。

这样做的好处是：类型、生命周期和拓扑仍然由 Rust 工具链守住。

## 进程内静态，进程间显式

Roplat 的进程内图是静态的：节点和边在编译期声明，宏展开为执行代码。

跨进程通信则显式使用 IPC：

- 进程内普通节点边：System DSL。
- 跨节律域状态：sideband primitives。
- 跨进程：IPC ring/triple buffer。
- 跨语言 native object：opaque message。

不要把所有通信都塞进 IPC，也不要把 sideband 当成普通 DSL 边的替代品。

## 多语言是构建期能力

Roplat 的 C++ / Python 支持尽量放在构建期完成：

- `#[roplat_msg]` 生成 C header、Python ctypes stub、schema。
- `#[roplat::node(lang = "...")]` 声明外部语言节点。
- `roplat_build` 两阶段提取 manifest，再生成文件。
- native C++ 编译由 `NativeBuildConfig` 管理。

这让 Rust 侧仍然能把 C++ / Python 节点当作有类型的节点使用。

## 当前边界要说清楚

好的文档应该明确边界。当前推荐下游使用：

- `Node` / `Rhythm` / `#[roplat::system]`
- `#[roplat_msg]`
- C++ / Python puppet node
- `roplat_build`
- sideband comm
- IPC MVP
- replay core API
- `cargo roplat` 的 validate / topology / expand / ipc 等工具

需要谨慎或视分支状态确认：

- `resource` 子系统目前在核心 facade 中未启用。
- `#[roplat::interface]` 依赖 resource，不应作为普通下游推荐入口。
- `#[system(record = ...)]` 这类更高层录制回放宏集成仍在演进。
- UDS / named pipe / 真共享内存 IPC 后端不是默认已完成能力。

## 与 ROS 2 的关系

Roplat 不是“更小的 ROS 2”，也不是试图覆盖 ROS 2 的全部生态。它更像一个适合高确定性进程内执行图的框架。

| 维度 | Roplat 倾向 | ROS 2 倾向 |
|---|---|---|
| 拓扑 | 编译期声明 | 运行时发现 |
| 节奏 | Rhythm 域 | Executor / callback |
| 类型 | Rust 泛型和生成绑定 | IDL / DDS schema |
| 多语言 | 构建期生成 glue | 各语言运行时客户端库 |
| 进程内通信 | 静态图和 lock-free sideband | DDS / rcl 层抽象 |

如果你的系统需要大规模动态发现，ROS 2 仍然有优势。如果你需要明确、可审查、可复现的控制/实验执行图，Roplat 的模型更直接。
