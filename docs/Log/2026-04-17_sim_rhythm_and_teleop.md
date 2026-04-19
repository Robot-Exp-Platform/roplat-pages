# 2026-04-17 SimRhythm 与遥操作架构

## SimRhythm

将原有的 `SimStepNode`（作为普通 Node 的仿真步进）重构为 `SimRhythm`——一个独立的节律源。

### 设计理由

物理仿真步进不是一个"处理输入→产出输出"的节点，而是一个**驱动时间前进**的源头。将其升级为 Rhythm 语义更正确：

- 每个 tick 先调用 `engine.step()` 推进物理世界
- 然后 yield `()` 给挂载在下游的观测/记录节点

### API

```rust
let sim_rhythm = SimRhythm::new(engine, Duration::from_secs_f64(1.0 / 240.0));
sim_rhythm >> { observer >> recorder; };
```

## 遥操作三例

### sim.rs — 纯仿真

三个节律域：

- 输入域 (~60Hz)：SpaceMouse → Mapper
- 控制域 (~1kHz)：Controller → Robot (仿真)
- 仿真域 (~240Hz)：SimRhythm 步进物理引擎

### real.rs — 真机

两个节律域：

- 输入域 (~60Hz)：SpaceMouse → Mapper
- 控制域 (~1kHz)：Controller → Robot (真实硬件)

### real_sim.rs — 真机 + 仿真镜像

在 real.rs 基础上增加仿真域，通过 `attach_from` 将真机的关节状态同步到仿真可视化。三个域并行运行。

## SpaceMouse Rust 原生 HID

替代之前的 Python + UDP 方案，使用 `hidapi` 直接读取 SpaceMouse 6DoF 数据。消除了 Python 进程管理和 UDP 延迟。
