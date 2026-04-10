# 2026-04-10 两遍扫描文件生成系统

## 工作概述

将 roplat 多语言文件生成从硬编码方式重构为两遍扫描（Two-pass）系统：
过程宏提取元数据 → build.rs 读取清单 → 代码生成器生成文件。

## 架构设计

### 两遍扫描流程

```
cargo build
│
├─ build.rs 启动（主进程）
│   ├─ 检查 ROPLAT_PHASE → 非 EXTRACT，进入编排模式
│   ├─ [Phase 1] 启动 cargo check --target-dir=roplat-extract
│   │   ├─ 子进程 build.rs 检测 ROPLAT_PHASE=EXTRACT → 直接退出
│   │   ├─ 编译器展开过程宏：
│   │   │   ├─ #[roplat_msg] → 写入 msg_*.json
│   │   │   ├─ #[roplat::node(lang = ...)] → 写入 node_*.json
│   │   │   └─ #[roplat::roplat_msg(lang = ...)] → 写入 opaque_*.json
│   │   └─ 子进程完成，5 个元文件已写入
│   │
│   └─ [Phase 2] 读取元文件，调用 MsgCodeGen/OpaqueCodeGen/NodeCodeGen
│       └─ 生成 12 个目标文件（8 基类 + 4 用户文件）
│
└─ Rust 正式编译
```

### 元文件格式

三种 JSON 清单类型，按 `"kind"` 字段区分：

- **msg**: `{kind, name, c_header, python_stub}` — 透明类型
- **opaque**: `{kind, name, fields[{name, rust_type}]}` — 不透明数据
- **node**: `{kind, name, lang, ports[{name, msg_type, direction}], fields[...]}` — 节点

## 新增组件

### roplat_macros

| 文件 | 说明 |
|------|------|
| `src/manifest_writer.rs` | 元文件写入工具（检测 ROPLAT_PHASE=EXTRACT + 写 JSON） |
| `src/puppet.rs` | `#[roplat::puppet]` 过程宏 — 多语言节点傀儡标注 |
| `src/opaque_attr.rs` | `#[roplat::opaque]` 过程宏 — 不透明数据傀儡标注 |

依赖新增：`serde_json = "1"`

### roplat_build

| 文件 | 说明 |
|------|------|
| `src/manifest.rs` | 元文件 JSON 结构定义 + 读取器 + 到 codegen 类型的转换 |
| `src/orchestrator.rs` | `BuildOrchestrator` — 两遍扫描编排器 |

依赖新增：`serde = { version = "1", features = ["derive"] }`, `serde_json = "1"`

### roplat 主 crate

`lib.rs` 新增：`pub use roplat_macros::{opaque, puppet};`

## 修改文件

### roplat_macros/src/msg.rs

在 `expand_roplat_msg` 中增加 EXTRACT 模式：生成 C header 和 Python stub 后写入元文件。

### roplat_macros/src/lib.rs

添加 3 个新模块声明和 2 个新过程宏入口（`puppet`, `opaque`）。

### examples/multi_lang/src/puppet.rs

三个傀儡结构添加过程宏属性：

```rust
#[roplat::puppet(lang = "cpp", input(sensor_input, SensorData), output(motor_output, MotorCommand))]
pub struct CppControllerPuppet { gain: f64, offset: f64 }

#[roplat::puppet(lang = "py", input(sensor_input, SensorData), output(plan_output, MotorCommand))]
pub struct PyPlannerPuppet { target_x: f64, target_y: f64, max_speed: f64 }

#[roplat::opaque]
pub struct CppDataPuppet { scale: f64, mode: i32 }
```

### examples/multi_lang/build.rs

从 ~230 行硬编码缩减为 ~30 行声明式调用：

```rust
fn main() {
    if std::env::var("ROPLAT_PHASE").as_deref() == Ok("EXTRACT") { return; }
    roplat_build::BuildOrchestrator::new().build().expect("...");
    println!("cargo:rerun-if-changed=src/");
}
```

## 测试

- 原有 21 个 codegen 测试全部通过
- 新增 7 个 manifest 测试：读取 msg/opaque/node、空目录、不存在目录、类型转换、多文件
- **共 28 测试全部通过**

## 技术要点

1. **避免 Cargo 锁死锁**：子进程 `cargo check` 使用 `CARGO_TARGET_DIR=target/roplat-extract/` 独立目标目录
2. **过程宏环境变量**：`ROPLAT_PHASE` 控制模式，`ROPLAT_MANIFEST_DIR` 指定写入路径
3. **幂等性**：每次构建清除旧元文件后重新提取；基类每次覆盖，用户文件仅首次生成
