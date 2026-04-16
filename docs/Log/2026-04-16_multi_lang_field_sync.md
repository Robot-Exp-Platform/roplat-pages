# 多语言字段同步与全链路贯通

**日期**: 2026-04-16

## 背景

chain_mixed 和 multi_lang 示例虽然能编译通过，但运行时 C++ 节点字段全为零——Rust 侧设置的 `scale=2.0` 等值从未同步到 C++ 对象。Python 桥接代码已由 puppet 宏完整生成，但因 C++ 上游字段失效导致整条链路输出 `fused=0.000`。

## 问题根因

C++ 节点的 `create()` FFI 函数分配对象后默认初始化字段为零。Rust puppet 结构体虽持有正确值（如 `scale=2.0`），但缺少将值推送到 C++ 对象的机制。

## 实现

### 1. codegen.rs — 生成 set_fields FFI

在 `write_cpp_ffi()` 中为每个有字段的 C++ 节点生成额外的 `set_fields` 函数：

```cpp
extern "C" void roplat_node_xxx_set_fields(void* ptr, type1 field1, type2 field2, ...) {
    auto* n = static_cast<XxxNode*>(ptr);
    n->setField1(field1);
    n->setField2(field2);
}
```

在 `write_cpp_base()` 中声明该函数的 FFI 原型。

### 2. puppet.rs — 宏注入 set_fields 调用

为 C++ puppet 节点生成：

- `set_fields_decl`：Rust 侧 FFI 声明 `fn set_fields(ptr: *mut c_void, field1: T1, ...)`
- `set_fields_call`：在 `on_init` 中 `create` 之后、`init` 之前调用

生命周期变为：`create → set_fields → init`。

### 3. 参数化构造器

puppet 的 `__roplat_ptr` 字段为私有，系统 DSL 不支持字段赋值语句。解决方案：在 puppet 模块内提供 `with_*()` 构造器。

### 4. multi_lang 示例修复

- 移除 6 个示例中系统宏体内的 `println!`（DSL 不支持宏调用）
- 移除 3 个示例中的裸块赋值 `let _ = { fwd.bias = 0.5; };`（DSL 不支持裸块）
- 改用 `PyForward::with_bias(0.5)` 参数化构造器

## 验证结果

### chain_mixed（Rust → C++ → C++ → Python → Python → Rust）

```
seq=1 fused=9.100   // (1.25*2+0.5)*3+0.1
seq=2 fused=16.600  // (2.50*2+0.5)*3+0.1
seq=3 fused=24.100  // (3.75*2+0.5)*3+0.1
```

### multi_lang 6 个示例

| 示例 | 预期 | 结果 |
|------|------|------|
| rs_cpp | 3.14×2.0=6.28 | PASS |
| rs_py | 3.14+0.5=3.64 | PASS |
| cpp_opaque | 3.14 round-trip | PASS |
| py_opaque | 3.14 round-trip | PASS |
| cpp_to_py | 1.0×2.0+0.5=2.5 | PASS |
| py_to_cpp | (1.0+0.5)×2.0=3.0 | PASS |

### 测试套件

roplat_build: 30 pass, roplat lib: 135 pass。

## 变更文件

| 文件 | 变更 |
|------|------|
| `roplat_build/src/codegen.rs` | 生成 `set_fields` FFI 函数和声明 |
| `roplat_macros/src/puppet.rs` | 注入 `set_fields` FFI 声明与 on_init 调用 |
| `examples/chain_mixed/src/puppet.rs` | 添加 `with_*()` 构造器 |
| `examples/chain_mixed/src/main.rs` | 使用参数化构造器 |
| `examples/chain_mixed/cpp/src/*.h` | 传播 seq 字段 |
| `examples/multi_lang/src/puppet.rs` | 添加 `with_bias()` 构造器 |
| `examples/multi_lang/examples/*.rs` (×6) | 移除 println!/裸块，改用构造器 |
| `roplat_build/tests/codegen_test.rs` | 更新 Python 用户文件断言 |
| `examples/macros/examples/hello_world.rs` | 更新 Rhythm::drive 签名 |
| `examples/file_launch/src/main.rs` | 移除 system 体内 println! |
