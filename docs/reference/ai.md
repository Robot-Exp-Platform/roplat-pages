# 与 AI 协作

[roplat-skills](https://github.com/Robot-Exp-Platform/roplat-skills) 是给 AI 编程助手使用的技能集合。本站帮助你理解设计、判断 AI 写得对不对；技能则给 AI 提供编码步骤、可运行的范例和核对清单。两者对应同一个 roplat 版本，可以一起使用。

| 技能 | 用途 |
|---|---|
| `roplat-development` | 用 Node / Rhythm / System 编写和修改 roplat 应用：节律分层、设备控制节律、资源借用、旁路、生命周期与执行结果 |
| `robot-behavior` | 使用或实现 robot_behavior 驱动：运动与控制能力、控制会话契约、roplat 适配 |

技能对应 crates.io 上的 roplat 0.5.0 与 robot_behavior 0.8.0，自带的范例只依赖这两个已发布的包。

## 把技能交给 AI

每个技能是一个独立目录，以 `SKILL.md` 为入口。工具支持加载技能时，按工具的方式加载这个目录；否则直接让 AI 阅读 `SKILL.md` 和它引用的材料。不依赖特定编辑器或全局安装。

可以复制下面的说明，填入你的需求：

```text
请先阅读 roplat-skills/skills/roplat-development/SKILL.md。
项目使用 roplat 0.5.0（见 Cargo.toml / Cargo.lock）。
任务：<要实现的功能>

应用组图请使用 #[roplat::system]，不要用手写的 process().await 链替代。
涉及多层节律时，先说明每层的 Input / Output、Yield / Feed，
以及哪些对象在外层保留、哪些在周期内创建、设备借给谁。
实现后运行有限的无设备版本，在调用方验证输出、状态和退出；如实报告没有验证的部分。
```

## 怎样判断 AI 写得对不对

- 应用用 `#[roplat::system]` 组图；节点实现 `Node::process`、节律实现 `Rhythm::drive` 是正常的，但应用层不应绕开 System 手写调用链或调度循环。
- 子节律每个周期的 Feed 与整次 drive 的 Output 没有混用。
- 设备通过 `.resources.N` 借用，没有放进 Input / Output，也没有归还边。
- 外层传入的对象没有被重新初始化或清空状态。
- 业务 `Result` 没有被擅自改成所有节点自动失败。
- 同一实例只有一个调用位置；重复由节律产生。
- 没有运行过的测试、设备或性能实验，没有被写成"已验证"。

用 [`cargo roplat graph`](../integrate/graph.md) 把 AI 写的图画出来，是检查结构最快的办法。

## 边界

开发技能不等于操作真实机器人的授权。设备专用参数、现场状态和凭据不应写进通用技能；连接真实设备之前，先在无设备的版本上验证。
