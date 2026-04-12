# 2026-04-13 旁路通讯 —— 环形队列有序消息传递

## 概述

实现了旁路通讯中的「环形队列」通讯方式。这是继三缓冲之后的第二种旁路通讯原语，覆盖 Rust 内核、C++ 封装、Python 封装、TypeBinding 多语言映射。

三缓冲用于状态同步（始终保持最新值，有损），环形队列用于事件流（FIFO 有序，可选有损）。两者共同构成旁路通讯的完整语义。

## 与三缓冲的对比

| 特性 | 三缓冲 | 环形队列 |
|------|--------|----------|
| 语义 | 状态同步（始终最新） | 事件流（FIFO 有序） |
| 拓扑 | SPMC（一写多读） | SPSC（单写单读） |
| 数据丢失 | 读端总是跳到最新，旧值被覆盖 | `try_push` 满时拒绝；`force_push` 满时丢弃最旧 |
| 读端行为 | `get_latest()` 返回 `Option<&T>`（借用） | `try_pop()` 返回 `Option<T>`（所有权转移） |
| 容量 | N 个订阅者 × 各自 2 个 buffer | 固定容量槽位数组 |
| 内存序 | Acquire/Release on ready pointer | Acquire/Release on head/tail |

## 设计决策

### 单调递增索引

head 和 tail 使用 `usize` 单调递增，通过 `head % capacity` 映射到实际槽位。`head.wrapping_sub(tail)` 即为当前元素数量。

优势：不需要额外的"满/空"标志位，也避免了经典环形队列浪费一个槽位来区分满和空的问题。

### SPSC 内存序

- 写端（push）：Relaxed 读 head → Acquire 读 tail → 写数据 → Release 写 head
- 读端（pop）：Relaxed 读 tail → Acquire 读 head → 读数据 → Release 写 tail

Acquire/Release 配对保证：写端写入数据对读端可见后，才更新 head；读端消费数据完成后，才推进 tail。

### force_push 的限制

`force_push` 在队列满时通过推进 tail 来丢弃最旧元素。这意味着写端同时修改了 tail，因此 **不能**与 `try_pop`（读端也修改 tail）并发使用。使用场景限于单线程或调用方自行保证互斥。

### memcpy 语义的 FFI 层

C FFI 层通过 `copy_nonoverlapping` 复制字节实现 push/pop，不依赖具体类型。这使得 C++ 和 Python 可以直接通过 FFI 操作任意 `#[repr(C)]` 结构体。

## 实现清单

### 1. Rust 环形队列内核 (`roplat/src/comm/ring_buffer.rs`)

- `RingBufferCtrl`：`#[repr(C)]` 控制块，`AtomicUsize` head/tail + capacity + slot_size + data 指针
- C FFI 接口：
  - `roplat_rb_new(capacity, slot_size)` → `*mut RingBufferCtrl`
  - `roplat_rb_destroy(ctrl)`
  - `roplat_rb_try_push(ctrl, src)` → `bool`
  - `roplat_rb_force_push(ctrl, src)`
  - `roplat_rb_try_pop(ctrl, dst)` → `bool`
  - `roplat_rb_len(ctrl)` → `usize`
  - `roplat_rb_capacity(ctrl)` → `usize`
- `RingBufferWriter<T>`：泛型写端，try_push / force_push / len / is_empty / is_full
- `RingBufferReader<T>`：泛型读端，try_pop（MaybeUninit，不要求 Default）/ len / is_empty
- `RingBufferChannel<T>`：带 Drop 的生命周期管理通道
- `create_ring_buffer<T>(capacity)` → `(Writer, Reader)` 便捷函数

### 2. C++ 封装 (`roplat_cpp/include/roplat/comm.h`)

- `roplat::comm::RingBufferWriter<T>`：move-only 模板，try_push / force_push / len / is_empty / is_full
- `roplat::comm::RingBufferReader<T>`：move-only 模板，try_pop 返回值类型 Option / len / is_empty
- `roplat::comm::RingBufferChannel<T>` + `create_ring_buffer<T>(capacity)` 工厂函数

### 3. Python 封装 (`roplat_py/src/comm.py`)

- `RingBufferWriter`：ctypes 封装，try_push / force_push / len / is_empty / is_full
- `RingBufferReader`：ctypes 封装，try_pop → `Optional[ctypes.Structure]` / len / is_empty
- `create_ring_buffer(ctype_struct, capacity)` 工厂函数
- 7 个 FFI 函数签名在 `_get_lib()` 和 `set_lib()` 中注册

### 4. TypeBinding 多语言映射 (`roplat/src/type_binding.rs`)

- `impl TypeBinding for RingBufferWriter<T>`：委托给 payload 类型 T
- `impl TypeBinding for RingBufferReader<T>`：委托给 payload 类型 T
- `impl TypeBinding for RingBufferChannel<T>`：委托给 payload 类型 T

容器类型透明/不透明由内部 payload 决定，可以作为节点字段参与代码生成。

## 测试

### 单元测试（8 个，全部通过）

- `test_basic_push_pop` — 基础 push/pop 和空队列 None
- `test_full_buffer` — 满时 try_push 返回 false，pop 后可继续写入
- `test_force_push_overwrites` — 满时 force_push 丢弃最旧
- `test_len_and_capacity` — len/is_empty/is_full 语义正确
- `test_repr_c_struct` — `#[repr(C)]` 结构体的字段级正确性
- `test_wraparound` — 10 轮填满+清空，触发索引回绕
- `test_spsc_threading` — 双线程 10,000 条消息 FIFO 有序性
- `test_channel_lifecycle` — RingBufferChannel 创建/使用/Drop

## 内存布局

```
RingBufferCtrl (#[repr(C)])
┌─────────────────────┐
│ head: AtomicUsize    │  写端持有
│ tail: AtomicUsize    │  读端持有
│ capacity: usize      │  槽位总数
│ slot_size: usize     │  每个槽位字节数
│ data: *mut u8 ───────┼──► [slot_0][slot_1]...[slot_{cap-1}]
└─────────────────────┘     alloc_zeroed, align = 8
```

## 注意事项

- `force_push` 不可与 `try_pop` 并发（均修改 tail），仅适用于单线程场景或调用方自行加锁
- 环形队列使用 `alloc_zeroed` 分配槽位数组，对齐为 8 字节
- pop 通过 `MaybeUninit<T>` 接收，不要求 `T: Default`
- 三层封装模式（Rust FFI 内核 → C++ 模板 → Python ctypes）与三缓冲完全一致
