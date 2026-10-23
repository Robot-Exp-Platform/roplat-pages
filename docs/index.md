---
hide:
  - navigation
---

# roplat

!!! warning "仍在快速迭代"
    roplat 的 API 还不稳定，任何版本之间都可能出现不兼容的变更，暂不建议用于生产环境。本站对应 **roplat 0.5.0**。

<div class="hero" markdown>

roplat 用 Rust 组织机器人程序：**Node** 完成一次计算或设备操作，**Rhythm** 决定什么时候取得状态、推进下一个周期，**System** 把它们连成一张图。`#[roplat::system]` 在编译期把这张图转换成 Rust 异步代码。

[安装并运行第一个程序](start/first-system.md){ .md-button .md-button--primary }
[学习路线](start/roadmap.md){ .md-button }

</div>

```rust
// 机械臂的控制节律每个周期给出状态，域内算出指令交回节律。
&mut arm >> control.resources.0;
control >> |state| {
    state >> planner;
    state >> servo.input.0;
    planner >> servo.input.1;
    servo
};
```

## 三个角色

| 角色 | 负责什么 | 你写什么 |
|---|---|---|
| Node | 一次输入到一次输出：滤波、控制律、规划、一次设备动作 | 实现 `Node::process` |
| Rhythm | 一个执行域怎样推进：何时开始一个周期、何时结束整次运行 | 选用内置节律，或实现 `Rhythm::drive` |
| System | 谁依赖谁、哪些对象属于哪一层、设备借给谁 | 在 `#[roplat::system]` 函数里连线 |

应用作者用 System 描述结构，不手写调度循环、通道和对象归还；节点和节律作者实现各自的 trait，不需要知道自己被接在图的什么位置。

## 从这里开始

<div class="grid cards" markdown>

- **第一次使用**

    安装工具链，运行一个完整的小程序，认识头段、图和尾段。

    [安装与第一个程序 →](start/first-system.md)

- **按机器人任务学**

    从节律的四个边界开始，逐步加入设备借用、分支、多层节律、停止与多设备。

    [教程 →](tutorial/rhythm-boundaries.md)

- **理解原理**

    每个概念为什么这样设计，边界在哪里。

    [概念 →](concepts/node.md)

- **查语法和诊断**

    连线写法、内置节律、常见编译错误和 0.4 迁移。

    [参考 →](reference/syntax.md)

</div>

## 设计取向

- **设备决定自己的节拍。** 控制节律在周期开始取得机器人状态，域内算完直接把指令交回；不必先让定时器发消息、再由消息触发控制。
- **进程内是编译期确定的静态图。** 节点、节律和连接在编译时可见；不同进程分别编译，经 IPC 连接。
- **创建位置就是生命周期。** 跨周期保留的对象在外层创建，每个周期的状态在周期内创建。
- **设备是借出的资源，不是消息。** 机械臂经 `&mut arm >> user.resources.0` 借给一次调用，用完即还，失败时也不会丢失。

静态图不等于硬实时，也不能证明任意程序没有死锁；节点里的阻塞调用、外语运行时和操作系统调度仍然会影响时序。详见[支持范围与已知问题](reference/scope.md)。

## 获取与许可

roplat 发布在 [crates.io](https://crates.io/crates/roplat)，API 文档在 [docs.rs](https://docs.rs/roplat/0.5.0/roplat/)。许可证为 PolyForm Noncommercial 1.0.0，商业使用前请先阅读许可条款。

给 AI 编程助手使用的技能集合见 [roplat-skills](https://github.com/Robot-Exp-Platform/roplat-skills)，用法见[与 AI 协作](reference/ai.md)。
