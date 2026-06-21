# 学习路线

这份文档按读者目标给出路线。你不需要先读完整个站点。

## 我只想跑起来

1. [快速开始总览](../QuickStart/00%20快速开始总览.md)
2. [从零创建 Rust 项目](../QuickStart/01%20从零创建%20Rust%20项目.md)
3. [节点 Node](../Concepts/01%20Node.md)
4. [节律 Rhythm](../Concepts/02%20Rhythm.md)
5. [系统 System](../Concepts/03%20System.md)

目标：能写一个 Rust-only pipeline，并理解为什么不手写循环。

## 我要接入 C++ 或 Python

1. 先完成 Rust-only pipeline。
2. 读 [多语言编译管线](../Architecture/01%20Pipeline.md)。
3. 读 [扩展 C++ 节点](../QuickStart/02%20扩展%20C++%20节点.md) 或 [扩展 Python 节点](../QuickStart/03%20扩展%20Python%20节点.md)。
4. 读 [实现数据互通](../QuickStart/04%20实现数据互通.md)。

目标：理解 Rust puppet、`roplat_build`、生成文件和用户文件的边界。

## 我要设计一个完整下游项目

1. [项目介绍](01%20Introduction.md)
2. [概念导读](../Concepts/00%20概念导读.md)
3. [快速开始总览](../QuickStart/00%20快速开始总览.md)
4. [架构总览](../Architecture/00%20Overview.md)
5. [CLI 工具](../Architecture/02%20CLI.md)

建议目录：

```text
my_robot/
  Cargo.toml
  build.rs              # 只有多语言/生成文件需要
  src/
    main.rs             # #[roplat::system]
    msg.rs              # #[roplat_msg]
    nodes.rs            # Rust Node
    puppet.rs           # C++ / Python puppet declarations
  cpp/
    src/                # user C++ files
    roplat_gen/         # generated, do not edit
  py/
    roplat_gen/         # generated, do not edit
```

## 我要做进程间通信

1. [通讯模型](../Concepts/04%20Comm.md)
2. [进程间通讯开发者参考](../Controbuction/12%20进程间通讯.md)
3. `examples/ipc_pubsub`
4. `cargo roplat ipc ls`
5. `cargo roplat ipc introspect <uri>`

目标：知道什么时候用 System DSL，什么时候用 sideband，什么时候用 IPC。

## 我要贡献 roplat 本身

1. [项目入门](../Controbuction/0%20项目入门.md)
2. [设计思想](../Controbuction/1%20设计思想.md)
3. [系统宏和图规约](../Controbuction/8%20图规约与系统宏.md)
4. 主仓 `TODO.md`
5. 对应源码目录

开发框架内部时再深入 `roplat_system`、`roplat_macros` 和 `roplat_build` 细节。普通下游用户不需要从这些实现细节开始。
