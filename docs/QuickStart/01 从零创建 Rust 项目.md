# 从零创建 Rust 项目

本章目标：在空目录中创建一个只依赖发布库的 Roplat Rust 工程。

## 1. 创建工程

```powershell
mkdir roplat-quickstart
cd roplat-quickstart
cargo new rust_starter
cd rust_starter
```

## 2. 安装依赖（不拉源码）

```powershell
cargo add roplat
```

## 3. 目标目录（tree）

完成本章后目录应为：

```text
rust_starter/
├─ Cargo.toml
└─ src/
   ├─ main.rs
   ├─ msg.rs
   └─ nodes.rs
```

## 4. 写消息 `src/msg.rs`

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

## 5. 写节点 `src/nodes.rs`

```rust
use crate::msg::{MotorCommand, SensorData};

pub struct SensorNode {
    sequence: u64,
}

impl SensorNode {
    pub fn new(start_seq: u64) -> Self {
        Self { sequence: start_seq }
    }

    pub fn tick(&mut self) -> SensorData {
        self.sequence += 1;
        SensorData {
            x: (self.sequence as f64 * 0.1).sin(),
            y: (self.sequence as f64 * 0.1).cos(),
            z: self.sequence as f64 * 0.01,
            timestamp: self.sequence,
        }
    }
}

pub struct MotorControllerNode {
    kp: f64,
}

impl MotorControllerNode {
    pub fn new() -> Self {
        Self { kp: 2.0 }
    }

    pub fn process(&mut self, input: &SensorData) -> MotorCommand {
        let error = (input.x * input.x + input.y * input.y).sqrt();
        MotorCommand {
            velocity: (error * self.kp) as f32,
            torque: (input.z * self.kp) as f32,
            position: error,
        }
    }
}
```

## 6. 写主程序 `src/main.rs`

```rust
mod msg;
mod nodes;

use roplat::comm::triple_buffer::create_triple_buffer;

fn main() {
    let (mut pub_sensor, mut sensor_subs) = create_triple_buffer::<msg::SensorData>(1);
    let (mut pub_motor, mut motor_subs) = create_triple_buffer::<msg::MotorCommand>(1);

    let mut sensor = nodes::SensorNode::new(0);
    let mut controller = nodes::MotorControllerNode::new();

    let sensor_data = sensor.tick();
    pub_sensor.publish(sensor_data.clone());

    if let Some(received) = sensor_subs[0].get_latest() {
        let command = controller.process(received);
        pub_motor.publish(command);
    }

    if let Some(cmd) = motor_subs[0].get_latest() {
        println!("MotorCommand: {:?}", cmd);
    }
}
```

## 7. 运行验证

```powershell
cargo run
cargo clippy --all-targets -- -D warnings
```

通过后进入 [扩展 C++ 节点](02%20扩展%20C++%20节点.md)。
