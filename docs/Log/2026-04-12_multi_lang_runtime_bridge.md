# 2026-04-12 多语言节点运行时桥接修复

## 工作概述

本次工作补齐了上一轮多语言节点任务中缺失的运行时桥接闭环，目标是让 Rust 侧傀儡节点可以调用 C++ 节点生命周期与处理函数，并完成输入输出类型的跨语言传递。

核心结论：

- C++ 路径已打通：`on_init`/`process`/`on_shutdown`/`drop` 均可走 FFI。
- Python 路径当前为存根：接口与调用位点已预留，等待 PyO3 集成。
- two-pass + codegen + C++ bridge 编译链路已验证可用。

## 关键变更

### 1. 傀儡节点宏运行时代码（`roplat_macros`）

在 `#[roplat::node(lang = ...)]` 正常编译模式下，自动生成：

- 隐藏指针字段 `__roplat_ptr: *mut c_void`
- `Default` 实现（将 `__roplat_ptr` 置空）
- `Drop` 实现（C++ 路径调用 destroy）
- `impl roplat::Node`：
  - `on_init` 调用 create/init
  - `process` 调用外部 process
  - `on_shutdown` 调用 shutdown

同时修复了 Rust 2024 兼容问题：

- `extern "C"` 改为 `unsafe extern "C"`
- `async_trait` 路径改为通过 `roplat` 重导出使用

### 2. 节点代码生成器（`roplat_build::NodeCodeGen`）

将 C++ 节点生成模型调整为双类结构：

- 系统文件 `<node>_base.h`：仅包含字段与 FFI 声明（roplat 管理）
- 用户文件 `<node>.h`：继承 `<Node>Base` 与 `roplat::Node<In, Out>`，实现 typed `process`

新增 `<node>_ffi.cpp` 生成：

- 实现 `create/destroy/init/shutdown/process` 五个 C ABI 函数
- 作为 Rust 与 C++ 用户类之间的桥接层

### 3. 示例工程构建流程（`examples/multi_lang`）

在 `build.rs` 中新增 Phase 3：

- 扫描 `cpp/roplat_gen/*_ffi.cpp`
- 使用 `cc` 编译桥接源文件
- 将生成目标与 Rust 产物一并链接

## 问题与修复

本轮排查并修复了以下阻断问题：

1. `E0753 expected outer doc comment`
   - 原因：`puppet.rs` 有残留内联文档块。
   - 修复：清理残留并重写该文件内容。

2. `extern blocks must be unsafe`
   - 原因：Rust 2024 edition 对 extern 块要求更严格。
   - 修复：宏输出调整为 `unsafe extern "C"`。

3. `cannot find async_trait` / `E0195`
   - 原因：示例 crate 未直接依赖 `async-trait`，宏使用了绝对路径 `::async_trait`。
   - 修复：`roplat` 重导出 `async_trait`，宏改为 `roplat::async_trait::async_trait`。

## 验证结果

- `cargo build -p multi_lang`：通过
- `cargo run -p multi_lang`：运行到示例结束（Windows 终端存在中文编码显示问题，但无 panic）
- `cargo test -p roplat_build`：`28 passed; 0 failed`

## 当前状态

- C++ 多语言节点链路：可用
- Python 多语言节点链路：接口已生成，运行时仍为 TODO（待 PyO3）
- two-pass 文件生成：稳定
