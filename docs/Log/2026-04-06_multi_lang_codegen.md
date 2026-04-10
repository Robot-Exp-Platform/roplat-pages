# 2026-04-06 多语言文件生成系统实现

## 概述

在 `roplat_build` 中实现了完整的多语言文件生成管线，覆盖三大类别：

1. **透明类型** (`MsgCodeGen`) — 已有，本次无重大改动
2. **不透明数据** (`roplat_msg(lang = ...)`) — 合并到消息宏，按语言生成单个用户文件
3. **多语言节点** (`NodeCodeGen`) — **新增**，为 C++/Python 节点生成带通讯端口的完整文件

## 新增 API

### NodeCodeGen

为多语言节点生成 4 个文件：

| 文件 | 位置 | 管理方 | 说明 |
|------|------|--------|------|
| `<node>_base.h` | `cpp/roplat_gen/` | roplat | C++ 基类：FFI 声明 + 端口 + 配置 + 虚函数 |
| `<node>.h` | `cpp/src/` | 用户 | C++ 用户类：继承基类，实现 process() |
| `<node>_base.py` | `py/roplat_gen/` | roplat | Python 基类：ABC + 端口 property + 配置 |
| `<node>.py` | `py/` | 用户 | Python 用户类：继承基类，实现 process() |

核心类型：

- `NodeSpec` — 节点描述，支持 builder 模式：`.input()` / `.output()` / `.field()`
- `NodePort` — 端口描述（名称、消息类型、方向）
- `PortDirection` — `Input` (Subscriber) / `Output` (Publisher)

使用示例：

```rust
let spec = NodeSpec::new("CppController")
    .input("sensor_input", "SensorData")
    .output("motor_output", "MotorCommand")
    .field(OpaqueField::f64("gain"))
    .field(OpaqueField::f64("offset"));

node_gen.generate_cpp(&spec)?; // 仅生成 C++ 文件
node_gen.generate_py(&spec)?;  // 仅生成 Python 文件
node_gen.generate_all(&spec)?; // 同时生成两种语言
```

### 不透明数据（合并后）

使用 `#[roplat::roplat_msg(lang = "cpp"|"py")]` 标注不透明结构，
每个类型仅生成一个用户文件，不再生成系统基类文件。

```rust
// 旧 API（向后兼容）：基类和用户在同目录
let cg = OpaqueCodeGen::new("out/cpp", "out/py");

#[roplat::roplat_msg(lang = "cpp")]
pub struct CppDataPuppet {
    scale: f64,
    mode: i32,
}
```

### OpaqueField 增强

新增便捷构造器：`OpaqueField::f32()`、`OpaqueField::u32()`、`OpaqueField::u64()`

## 目录结构

`multi_lang` 示例执行 `build.rs` 后的文件布局：

```
multi_lang/
├── cpp/roplat_gen/              # 系统管理，每次构建覆盖
│   │   ├── sensor_data.h               # MsgCodeGen: 透明类型
│   │   ├── motor_command.h             # MsgCodeGen: 透明类型
│   │   └── cpp_controller_base.h       # NodeCodeGen: 节点基类 (含端口)
├── py/roplat_gen/
│   └── py_planner_base.py              # NodeCodeGen: 节点基类 (含端口)
├── cpp/src/                      # 用户文件，仅首次生成
│   ├── cpp_data.h                      # roplat_msg(lang="cpp"): 用户文件（单文件）
│   └── cpp_controller.h               # NodeCodeGen: 用户实现 process()
└── py/                           # 用户文件，仅首次生成
    └── py_planner.py                   # NodeCodeGen: 用户实现 process()
```

## C++ 节点基类生成内容

以 `CppController` 为例，生成的 `cpp_controller_base.h` 包含：

- **FFI 函数声明**：`roplat_node_cpp_controller_create/destroy/process`
- **基类 `CppControllerBase`**：
  - 配置字段 `gain`, `offset` + getter/setter
  - 通讯端口 `Subscriber<SensorData>* sensor_input` / `Publisher<MotorCommand>* motor_output`
  - 端口 getter：`get_sensor_input()`, `get_motor_output()`
  - 纯虚函数：`virtual void process() = 0`
  - 生命周期：`virtual void on_init()`, `virtual void on_shutdown()`

用户文件 `cpp_controller.h` 继承基类并提供 `process()` 占位实现。

## Python 节点基类生成内容

以 `PyPlanner` 为例，生成的 `py_planner_base.py` 包含：

- 继承 `ABC`，`process()` 为 `@abstractmethod`
- 配置字段直接作为实例属性
- 通讯端口以 `@property` 暴露（私有 `_xxx` 属性由运行时注入）

## 测试

`roplat_build/tests/codegen_test.rs` 共 21 个功能测试：

- MsgCodeGen: 3 个（写 C 头文件/Python 存根/批量写入）
- OpaqueCodeGen: 6 个（旧 API 兼容/新 API 目录分离/内容验证/用户文件不覆盖）
- NodeCodeGen: 10 个（builder 模式/C++ Base/C++ User/Py Base/Py User/不覆盖/全量生成/C++ Only/Py Only）
- OpaqueField: 1 个（所有便捷构造器）
- to_snake_case: 1 个

全部通过 ✅

## 关键设计决策

1. **用户文件保护**：`write_cpp_user` / `write_py_user` 检查文件是否存在，仅首次生成
2. **相对路径计算**：C++ 用户文件 `#include` 使用相对路径指向基类（如 `../roplat_gen/...`）
3. **Python import**：由于 Python 无法直接用相对路径 import，fallback 使用模块名（需配合 `PYTHONPATH` 或 `sys.path`）
4. **`gen` 保留关键字**：Rust 2024 edition 中 `gen` 为保留关键字，测试代码中使用 `cg` 作为变量名
