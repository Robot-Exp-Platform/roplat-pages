# 扩展 Python 节点

本章在上一章基础上增加 Python 节点镜像。

## 1. 扩展 `src/puppet.rs`

追加：

```rust
#[roplat::node(
    lang = "py",
    input(sensor_input, SensorData),
    output(plan_output, MotorCommand),
)]
pub struct PyPlanner {
    pub target_x: f64,
    pub target_y: f64,
    pub max_speed: f64,
}

impl PyPlanner {
    pub fn new() -> Self {
        Self {
            target_x: 0.0,
            target_y: 0.0,
            max_speed: 1.0,
            ..Self::default()
        }
    }
}
```

## 2. 扩展 `main.rs`

```rust
let mut py = puppet::PyPlanner::new();
py.target_x = 10.0;
py.target_y = 20.0;
py.max_speed = 5.0;
println!("PyPlanner target=({}, {})", py.target_x, py.target_y);
```

## 3. 生成后目录（tree）

```text
rust_starter/
└─ py/
   ├─ roplat_gen/
   │  └─ py_planner_base.py
   └─ py_planner.py
```

## 4. 验证

```powershell
cargo build
cargo run
```

通过后进入 [实现数据互通](04%20实现数据互通.md)。
