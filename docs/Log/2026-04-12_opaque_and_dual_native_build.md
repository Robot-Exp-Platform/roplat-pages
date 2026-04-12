# 2026-04-12 不透明类型空壳化与双本地编译链

## 工作概述

本次工作完成了两项结构性调整：

1. 不透明类型（opaque data）不再由 Rust 定义内部字段，也不再在 Rust 侧提供构造入口。
2. 多语言本地编译链从示例内硬编码 `cc` 调用，收敛为 `roplat_build` 内统一管理的双后端：`cc` 与 `cmake`。

目标是降低用户心智负担：

- Rust 侧只声明“存在这样一个外部类型”。
- 用户只需要在 `build.rs` 里选择 native backend，并补充必要的附加源 / include / 依赖。

## 不透明类型改造

### 设计落点

`#[roplat::roplat_msg(lang = "cpp" | "py")]` 在 opaque 模式下改为：

- Rust 侧展开为空壳标记结构，不保留业务字段。
- 过程宏仍可在提取阶段写出 manifest。
- 代码生成默认只生成用户文件模板，不再依赖系统基类。

### 当前行为

- Rust 示例中的 `CppData` 改为仅保留类型声明。
- C++ / Python 用户文件成为 opaque 的唯一权威实现位置。
- 生成模板优先采用“直接在用户类里填写字段”的方式。
- 注释中保留“alias / wrapper 到其它项目内真实类型”的可选方案。

### 兼容处理

为避免旧模型残留误导，opaque 用户文件生成时会清理旧的 `*_base.h` / `*_base.py`。

## 双本地编译链

### 新增统一配置层

在 `roplat_build` 中新增：

- `NativeBackend`：`Cc` / `CMake`
- `NativeBuildConfig`：统一描述本地编译输入
- `NativePackage`：描述 CMake `find_package(...)` 依赖

`BuildOrchestrator` 新增 `native_build(...)` 配置入口，完成：

1. two-pass manifest 提取
2. 代码生成
3. native backend 编译与链接

### `cc` 后端

- 自动扫描 `cpp/roplat_gen/*_ffi.cpp`
- 自动探测 `roplat_cpp/include`
- 支持额外 `source` / `include_dir` / `define` / `link_lib`

### `cmake` 后端

- 自动生成 `cpp/roplat_gen/CMakeLists.txt`
- 使用 `cmake` crate 调起配置与构建
- 支持 `find_package(...)` 与 `target_link_libraries(...)`
- 修正了 Windows MSVC 多配置生成器下静态库链接目录问题

## 示例工程调整

`examples/multi_lang` 做了以下更新：

- `build.rs` 改为调用 `BuildOrchestrator::native_build(...)`
- 默认后端为 `cc`，可通过 `ROPLAT_NATIVE_BACKEND=cmake` 切换到 CMake
- 新增 `cpp/src/support/controller_math.h/.cpp` 作为附加本地源，用于验证两种后端都能编译用户补充的 C++ 代码
- `cpp_controller.h` 改为调用 `compute_motor_command(...)`
- `CppData` 在 Rust 侧改为仅保留类型标记
- `main.rs` 改为展示 opaque 类型的“Rust 仅保留标记”语义

## 验证结果

本次改造完成后验证如下：

- `cargo test -p roplat_build`：通过（30 个 codegen 测试 + 2 个 native build 测试）
- `cargo build -p multi_lang`：通过（`cc` 后端）
- `cargo run -p multi_lang`：通过
- `ROPLAT_NATIVE_BACKEND=cmake cargo build -p multi_lang`：通过
- `cargo clippy --workspace --all-targets -- -D warnings`：通过

## 结论

当前多语言路径已形成更清晰的职责边界：

- transparent type：Rust 定义布局，roplat 生成系统文件
- node puppet：Rust 提供字段与 typed process 桥接，roplat 生成系统基类与 FFI
- opaque type：Rust 仅保留类型名，用户在目标语言侧完成真实实现

native build 也已从示例级硬编码脚本，提升为 `roplat_build` 的统一能力层。
