# 2026-04-13 multi_lang 全矩阵测试与 C++ 不透明总线

## 工作概述

在 `examples/multi_lang` 中构建完整的跨语言通信测试矩阵，覆盖所有 Rust/C++/Python 两两之间的透明数据传递以及 C++/Python 各自内部的不透明数据通信。共 6 个 example，全部通过。

过程中发现并修复了 C++ 不透明类型 FFI 返回值 ABI 不匹配导致的 SEGFAULT，引入 **C++ 不透明总线 (opaque bus)** 机制。

## 测试矩阵

| Example | 管线 | 验证目标 |
|---------|------|----------|
| `rs_cpp` | Rust → CppForward(×2) → Rust | rs ↔ cpp 透明 |
| `rs_py` | Rust → PyForward(+0.5) → Rust | rs ↔ py 透明 |
| `cpp_to_py` | Rust → CppForward(×2) → PyForward(+0.5) → Rust | cpp → py 透明 |
| `py_to_cpp` | Rust → PyForward(+0.5) → CppForward(×2) → Rust | py → cpp 透明 |
| `cpp_opaque` | Rust → CppEncode → CppDecode → Rust | cpp 内部不透明 |
| `py_opaque` | Rust → PyEncode → PyDecode → Rust | py 内部不透明 |

透明消息类型 `Packet { id: u64, value: f64 }`，`#[repr(C)]` 数值可按指针跨 FFI 传递。

## 工程结构

以 library crate 组织，节点和数据定义在 `src/`，测试调用在 `examples/`：

```
multi_lang/
  src/
    lib.rs          # pub mod msg, nodes, puppet
    msg.rs          # SensorData, MotorCommand, Packet
    nodes.rs        # 纯 Rust 节点 (SensorNode, MotorControllerNode)
    puppet.rs       # 9 个傀儡节点 + 2 个不透明类型
  examples/
    rs_cpp.rs / rs_py.rs / cpp_to_py.rs / py_to_cpp.rs
    cpp_opaque.rs / py_opaque.rs
  cpp/src/
    cpp_forward.h   # 透明转发：value × 2.0
    cpp_encode.h    # Packet → CppData (payload = value × 10)
    cpp_decode.h    # CppData → Packet (value = payload / 10)
    cpp_data.h      # { uint64_t id; double payload; }
  py/
    py_forward.py   # 透明转发：value + bias
    py_encode.py    # Packet → PyData (payload = value × 100)
    py_decode.py    # PyData → Packet (value = payload / 100)
    py_data.py      # class PyData(id, payload)
```

## 核心修复：C++ 不透明总线

### 问题根因

`#[roplat_msg(lang="cpp")]` 在 Rust 侧生成 ZST 空壳：

```rust
struct CppData { __roplat_private: () }  // size = 0
```

C++ 侧 `CppData` 有实际大小（16 字节：`uint64_t + double`）。FFI 按值返回时：

- x64 Windows MSVC：16 字节返回通过隐藏输出指针（caller 分配栈空间并传指针）
- Rust 认为返回的是 ZST，**不分配任何栈空间**也不传隐藏指针
- C++ 写入 16 字节 → 踩栈 → `STATUS_ACCESS_VIOLATION (0xC0000005)`

chain_mixed 中 `CppOpaquePacket` 仅 8 字节（一个 double），恰好适配寄存器返回约定，"意外"能工作。

### 解决方案

引入 C++ 不透明总线，与 Python 的 `OPAQUE_BUS` 线程本地 HashMap 对称：

**codegen.rs (`write_cpp_ffi`)**：

对节点的 opaque 端口生成 `inline` 函数封装的 `thread_local` 存储，确保跨翻译单元共享：

```cpp
inline CppData& __roplat_opaque_bus_CppData() {
    static thread_local CppData instance;
    return instance;
}
```

FFI process 签名按 4 种 opaque 组合分支：

| (input_opaque, output_opaque) | FFI 签名 | 行为 |
|-------------------------------|----------|------|
| (true, true) | `void process(void*)` | 从总线读 → 处理 → 写回总线 |
| (false, true) | `void process(void*, const T*)` | 透明输入 → 结果存入总线 |
| (true, false) | `T process(void*)` | 从总线读 → 返回透明输出 |
| (false, false) | `T process(void*, const U*)` | 原始直传 |

**codegen.rs (`write_cpp_base`)**：

base header 中 `extern "C"` 声明同步匹配，避免 MSVC C2733 重载冲突。

**puppet.rs**：

Rust 侧 `extern "C"` 声明和 `process()` 调用按同样的 4 分支生成，ZST 类型不再出现在 FFI 返回位置。

### 辅助方法

`NodePort` 新增 `is_opaque()`，`NodeSpec` 新增 `input_is_opaque()` / `output_is_opaque()`，通过端口名 `contains("opaque")` 判定。

### 关键设计选择

使用 `inline` 函数（C++17 `inline` 变量语义）而非 `static thread_local` 变量。原因：

- `static thread_local` 在每个 `.cpp` 翻译单元中创建独立副本
- `inline` 保证 ODR 唯一性：encode 和 decode 的 FFI 文件共享同一份 `thread_local` 实例
- `/std:c++17` 已在构建链中启用

## 验证

- 6/6 examples 全部 PASS
- `cargo run -p chain_mixed`：EXIT 0（向后兼容）
- `cargo test -p roplat_macros --quiet`：33/33 通过
