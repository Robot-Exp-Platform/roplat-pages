# 从零创建 Rust 项目

本章目标：从空目录开始，创建一个包含消息定义、节点实现和 System DSL 的完整 Roplat 项目。

## 1. 创建工程

```powershell
mkdir roplat-quickstart
cd roplat-quickstart
cargo new rust_starter
cd rust_starter
```

## 2. 安装依赖

```powershell
cargo add roplat
cargo add tokio --features full
```

## 3. 目标目录结构

```text
rust_starter/
├─ Cargo.toml
└─ src/
   ├─ main.rs
   ├─ msg.rs
   └─ nodes.rs
```

## 4. 定义消息 `src/msg.rs`

消息是节点之间传递的数据结构。使用 `#[roplat::roplat_msg]` 标记，并加上 `#[repr(C)]` 以支持跨语言访问：

```rust
#[roplat::roplat_msg]
#[repr(C)]
#[derive(Clone, Debug, PartialEq)]
pub struct SensorData {
    pub x: f64,
    pub y: f64,
    pub z: f64,
    pub timestamp: u64,
}

#[roplat::roplat_msg]
#[repr(C)]
#[derive(Clone, Debug, PartialEq)]
pub struct MotorCommand {
    pub velocity: f32,
    pub torque: f32,
    pub position: f64,
}
```

## 5. 实现节点 `src/nodes.rs`

节点实现 `Node` trait——定义输入输出类型，实现 `process` 方法：

```rust
use roplat::node::Node;
use roplat::error::RoplatError;
use crate::msg::{MotorCommand, SensorData};

/// 传感器节点：每次调用产生一帧传感器数据
pub struct SensorNode {
    sequence: u64,
}

impl SensorNode {
    pub fn new() -> Self {
        Self { sequence: 0 }
    }
}

impl Node for SensorNode {
    type Input = ();               // 无需外部输入
    type Output = SensorData;      // 产出传感器数据
    type Error = RoplatError;

    async fn process(&mut self, _: ()) -> SensorData {
        self.sequence += 1;
        SensorData {
            x: (self.sequence as f64 * 0.1).sin(),
            y: (self.sequence as f64 * 0.1).cos(),
            z: self.sequence as f64 * 0.01,
            timestamp: self.sequence,
        }
    }
}

/// 控制器节点：接收传感器数据，输出电机指令
pub struct ControllerNode {
    kp: f64,
}

impl ControllerNode {
    pub fn new(kp: f64) -> Self {
        Self { kp }
    }
}

impl Node for ControllerNode {
    type Input = SensorData;
    type Output = MotorCommand;
    type Error = RoplatError;

    async fn process(&mut self, input: SensorData) -> MotorCommand {
        let error = (input.x * input.x + input.y * input.y).sqrt();
        MotorCommand {
            velocity: (error * self.kp) as f32,
            torque: (input.z * self.kp) as f32,
            position: error,
        }
    }
}

/// 打印节点：接收电机指令并打印
pub struct PrintNode;

impl Node for PrintNode {
    type Input = MotorCommand;
    type Output = ();
    type Error = RoplatError;

    async fn process(&mut self, input: MotorCommand) -> () {
        println!("Motor: vel={:.2}, torque={:.2}, pos={:.4}",
            input.velocity, input.torque, input.position);
    }
}
```

!!! tip "关键点"
    - 节点只关心 `Input → Output` 转换，不关心何时被调用
    - `async fn process` 是原生异步方法，可以在内部使用 `.await`
    - 无需手动注册——system DSL 会自动编排

## 6. 组装系统 `src/main.rs`

### 方式 A：使用旁路通讯（手动组装）

最基础的方式，手动创建通讯通道和节律源：

```rust
mod msg;
mod nodes;

use roplat::comm::triple_buffer::create_triple_buffer;
use roplat::node::Node;

#[tokio::main]
async fn main() {
    // 创建通讯通道
    let (mut pub_sensor, mut sensor_subs) =
        create_triple_buffer::<msg::SensorData>(1);
    let (mut pub_motor, mut motor_subs) =
        create_triple_buffer::<msg::MotorCommand>(1);

    // 实例化节点
    let mut sensor     = nodes::SensorNode::new();
    let mut controller = nodes::ControllerNode::new(2.0);
    let mut printer    = nodes::PrintNode;

    // 手动驱动一帧
    let data = sensor.process(()).await;
    pub_sensor.publish(data.clone());

    if let Some(received) = sensor_subs[0].get_latest() {
        let cmd = controller.process(received.clone()).await;
        pub_motor.publish(cmd);
    }

    if let Some(cmd) = motor_subs[0].get_latest() {
        printer.process(cmd.clone()).await;
    }
}
```

### 方式 B：使用 System DSL（推荐）

用 `#[roplat::system]` 宏声明式地描述数据流，编译期自动生成调度代码：

```rust
mod msg;
mod nodes;

use roplat::rhythm::CountRhythm;

#[roplat::system]
async fn main() {
    let mut sensor     = nodes::SensorNode::new();
    let mut controller = nodes::ControllerNode::new(2.0);
    let mut printer    = nodes::PrintNode;

    // CountRhythm 执行 10 次
    let (_, mut rhythm) = roplat::rhythm::create_count_rhythm(10);

    rhythm >> {
        sensor >> controller >> printer;
    };
}
```

!!! info "`>>` 做了什么"
    `sensor >> controller >> printer` 被编译为：
    ```rust
    let out1 = sensor.process(event).await;
    let out2 = controller.process(out1).await;
    printer.process(out2).await;
    ```
    没有动态分发，没有运行时查表。`>>` 只是编译期的代码生成指令。

## 7. 运行验证

```powershell
cargo run
```

预期输出（10 帧）：

```text
Motor: vel=0.20, torque=0.02, pos=0.1000
Motor: vel=0.40, torque=0.04, pos=0.1990
Motor: vel=0.59, torque=0.06, pos=0.2955
...
```

```powershell
# 代码质量检查
cargo clippy --all-targets -- -D warnings
cargo test
```

## 8. 使用定时器节律源

将 `CountRhythm` 替换为 `SysTimer`，让系统以固定频率持续运行：

```rust
use std::time::Duration;
use roplat::rhythm::SysTimer;

#[roplat::system]
async fn main() {
    let mut sensor     = nodes::SensorNode::new();
    let mut controller = nodes::ControllerNode::new(2.0);
    let mut printer    = nodes::PrintNode;

    // 100Hz 定时器
    let mut timer = SysTimer::new(Duration::from_millis(10));

    timer >> {
        sensor >> controller >> printer;
    };
}
```

系统将以 100Hz 持续运行，直到进程被终止（Ctrl+C）。

## 下一步

- [扩展 C++ 节点](02%20扩展%20C++%20节点.md) — 添加 C++ 实现的节点
- [扩展 Python 节点](03%20扩展%20Python%20节点.md) — 添加 Python 实现的节点
