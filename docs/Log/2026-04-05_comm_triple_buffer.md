# 2026-04-05 旁路通讯 —— 三缓冲状态更新实现

## 概述

实现了旁路通讯中的「三缓冲状态更新」通讯方式，覆盖 Rust 内核、C++ 封装、Python 封装、透明类型过程宏、build.rs 代码生成、不透明数据支持。

## 实现清单

### 1. Rust 三缓冲内核 (`roplat/src/comm/triple_buffer.rs`)

- `TripleBufferCtrl`：`#[repr(C)]` 的原子控制块，内持 `AtomicPtr<c_void>` 作为 ready 槽位
- C FFI 接口：`roplat_tb_ctrl_new`, `roplat_tb_ctrl_destroy`, `roplat_tb_swap`
- `Publisher<T>`：SPMC 广播发布者，支持惰性内存分配
- `Subscriber<T>`：订阅者，通过 `get_latest()` 获取 `Option<&T>`
- `TripleBufferChannel<T>`：带生命周期管理的通道（管理控制块所有权）
- `create_triple_buffer<T>(n)`：便捷创建函数

### 2. 不透明数据支持 (`roplat/src/comm/opaque.rs`)

- `OpaqueData`：傀儡结构，持有外部语言指针和 `DestroyFn`，Drop 时自动调用释放
- `TypedOpaque<T>`：泛型标记包装，编译期区分不同不透明数据类型
- C FFI：`roplat_opaque_create`, `roplat_opaque_destroy`, `roplat_opaque_get_ptr`, `roplat_opaque_get_size`

### 3. 透明类型过程宏 (`roplat_macros/src/msg.rs`)

- `#[roplat_msg]` 属性宏：要求结构体标注 `#[repr(C)]`
- 编译时生成 `C_HEADER` 和 `PYTHON_STUB` 常量字符串
- 支持基本类型映射（f32→float, f64→double, u32→uint32_t 等）
- 支持定长数组字段（`[f32; 4]` → `float data[4];` / `ctypes.c_float * 4`）

### 4. build.rs 代码生成 (`roplat_build/src/codegen.rs`)

- `MsgCodeGen`：将过程宏生成的头文件/存根写入文件系统
- `OpaqueCodeGen`：为不透明类型生成 C++ 基类 + 用户文件、Python 基类 + 用户文件
  - 基类文件由 roplat 管理，持续更新
  - 用户文件仅在不存在时生成（不会覆盖用户代码）
- `OpaqueField`：字段描述，提供 `f64()`, `i32()`, `bool()` 等便捷构造

### 5. C++ 封装 (`roplat_cpp/include/roplat/comm.h`)

- `roplat::comm::Subscriber<T>`：模板订阅者，返回 `Option` 类型
- `roplat::comm::Publisher<T>`：模板发布者，支持非默认构造类型
- `roplat::comm::create_triple_buffer<T>(n)`：便捷创建

### 6. Python 封装 (`roplat_py/src/comm.py`)

- `Subscriber`：ctypes 封装的订阅者，返回 `Optional[Structure]`
- `Publisher`：ctypes 封装的发布者，自动管理内存防 GC
- `create_triple_buffer(ctype_struct, n)`：便捷创建
- 延迟加载共享库，支持 `ROPLAT_LIB_PATH` 环境变量

## 测试

### 单元测试（7 个，全部通过）

- `comm::triple_buffer::tests::test_basic_publish_subscribe`
- `comm::triple_buffer::tests::test_spmc_broadcast`
- `comm::triple_buffer::tests::test_lazy_allocation`
- `comm::triple_buffer::tests::test_repr_c_struct`
- `comm::opaque::tests::test_opaque_data_lifecycle`
- `comm::opaque::tests::test_typed_opaque`
- `comm::opaque::tests::test_ffi_interface`

### 集成测试（17 个，全部通过）

- 透明类型通讯（SensorData, MotorCommand, JointState）
- SPMC 广播到多个订阅者
- 惰性内存分配（无默认构造、收敛性）
- TripleBufferChannel 生命周期管理
- 多线程发布/订阅（单调性验证）
- 不透明数据创建/销毁/FFI
- `#[roplat_msg]` C 头文件生成验证
- `#[roplat_msg]` Python 存根生成验证
- 宏生成类型与三缓冲结合通讯
- 语言内不透明类型通讯

## 注意事项

- SPMC 三缓冲中，多个订阅者在同一次 `publish` 中可能看到不同版本的值（by design，因为交换是串行的）
- 项目中 `node` 模块存在预先的编译错误（`viz` 依赖被注释的 `resource`，多个节点的 `process` 返回类型不匹配）。本次工作未修改这些问题
- Rust Edition 2024 要求 `#[no_mangle]` 使用 `#[unsafe(no_mangle)]`，`unsafe extern "C" fn` 内部需要显式 `unsafe {}` 块
