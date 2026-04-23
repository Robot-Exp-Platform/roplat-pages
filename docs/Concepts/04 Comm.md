# 通讯模型

Roplat 的节点间数据传递分为两条路径：**主流通讯**和**旁路通讯**。

## 主流通讯

主流通讯是 system DSL 中 `>>` 操作符声明的数据流——节点的 `Output` 直接作为下一个节点的 `Input`：

```rust
sensor >> filter >> controller >> motor;
//  Output ─→ Input ─→ Output ─→ Input
```

特征：

- **编译期确定**：类型在编译期匹配，连接在编译期建立
- **零开销**：直接值传递（`.process(input).await`），无序列化、无拷贝
- **强类型**：`sensor.Output` 必须与 `filter.Input` 类型一致，否则编译报错
- **域内使用**：主流通讯只在同一节律域内有效

## 旁路通讯

旁路通讯用于**跨节律域**的数据交换和**状态共享**。Roplat 提供两种 lock-free 原语：

### 三缓冲（Triple Buffer）

**语义**：写端始终更新最新值，读端始终获取最新快照。写端永远不阻塞。

```rust
use roplat::comm::create_triple_buffer;

// 创建：1 个写端 + N 个读端
let (mut publisher, mut subscribers) = create_triple_buffer::<SensorData>(3);

// 写端：发布最新数据
publisher.publish(SensorData { x: 1.0, y: 2.0, z: 3.0 });

// 读端：获取最新值
if let Some(data) = subscribers[0].get_latest() {
    println!("Latest: {:?}", data);
}
```

!!! info "有损语义"
    三缓冲是**有损**的——如果写端更新频率高于读端，中间值会被覆盖。读端总是获取最新的那一帧，而不是逐帧接收。这正是传感器状态同步所需要的语义。

适用场景：

- 传感器状态发布（IMU、关节角度、位姿）
- 全局参数广播
- 任何"只关心最新值"的场景

### 环形队列（Ring Buffer）

**语义**：FIFO 有序队列，SPSC（单生产者单消费者），无锁。

```rust
use roplat::comm::create_ring_buffer;

// 创建：容量 64 的环形队列
let (mut producer, mut consumer) = create_ring_buffer::<Command>(64);

// 写端：推入数据
producer.try_push(Command::MoveForward(1.0));

// 读端：弹出数据（FIFO 顺序）
while let Some(cmd) = consumer.try_pop() {
    execute(cmd);
}
```

!!! info "无损语义"
    环形队列是**无损**的——每条消息都会被消费，按 FIFO 顺序。如果队列满了，`try_push` 会失败（不覆盖旧数据）。

适用场景：

- 命令序列传递
- 事件日志
- 任何需要"每条消息都不能丢"的场景

### 对比

| 特性 | 三缓冲 | 环形队列 |
|:-----|:------|:--------|
| **拓扑** | SPMC（1 写 N 读） | SPSC（1 写 1 读） |
| **语义** | 最新值覆盖（有损） | FIFO 有序（无损） |
| **阻塞** | 写端永不阻塞 | 队列满时 push 失败 |
| **读操作** | `get_latest()` | `try_pop()` |
| **适用** | 状态同步 | 命令/事件流 |
| **锁** | Lock-free（原子操作） | Lock-free（原子操作） |

## 跨语言通讯

两种通讯原语都通过三层封装实现跨语言透明访问：

```text
┌─────────────────────────────────────────┐
│  Layer 3: Python ctypes 封装             │
│  roplat_py/src/comm.py                  │
├─────────────────────────────────────────┤
│  Layer 2: C++ 模板封装                    │
│  roplat_cpp/include/roplat/comm.h       │
├─────────────────────────────────────────┤
│  Layer 1: Rust FFI 内核                  │
│  #[repr(C)] + extern "C"               │
│  roplat/src/comm/                       │
└─────────────────────────────────────────┘
```

在 Rust 中创建的通讯实例，C++ 和 Python 节点可以直接读写——**共享同一块内存，无序列化开销**。

## 类型系统

通讯中传递的消息类型分为两种：

### 透明类型

使用 `#[repr(C)]` 布局，所有字段跨语言可见：

```rust
#[roplat::roplat_msg]
#[repr(C)]
#[derive(Clone, Debug)]
pub struct SensorData {
    pub x: f64,
    pub y: f64,
    pub z: f64,
    pub timestamp: u64,
}
```

构建系统自动生成对应的 C 头文件和 Python ctypes 结构：

=== "C++ (自动生成)"

    ```cpp
    struct SensorData {
        double x;
        double y;
        double z;
        uint64_t timestamp;
    };
    ```

=== "Python (自动生成)"

    ```python
    class SensorData(ctypes.Structure):
        _fields_ = [
            ("x", ctypes.c_double),
            ("y", ctypes.c_double),
            ("z", ctypes.c_double),
            ("timestamp", ctypes.c_uint64),
        ]
    ```

### 不透明类型

Rust 侧只是空壳标记，实际字段由目标语言定义：

```rust
#[roplat::roplat_msg(lang = "cpp")]
pub struct CppInternalData;  // 字段由 C++ 用户代码定义
```

不透明数据通过**线程本地总线**跨语言边界传递，避免序列化开销。适用于语言私有的复杂数据结构（如 OpenCV Mat、PyTorch Tensor）。

## system DSL 中的自动通道

当两个节律域之间存在数据流时，编译期图规约（R4 规则）会自动在边界处插入通道：

```rust
#[roplat::system]
async fn robot() {
    let mut sensor = Sensor::new();
    let mut ctrl   = Controller::new();

    // 域 1：快速传感
    timer_1khz >> {
        sensor;  // sensor 的输出需要传给 ctrl
    };

    // 域 2：慢速控制
    timer_100hz >> {
        ctrl;    // ctrl 的输入来自 sensor
    };
}
```

编译期自动生成：

```text
sensor ──[triple_buffer/ring_buffer]──→ ctrl
         ^^ 自动插入，用户无需手动创建
```

## 设计要点

1. **主流通讯零开销** — 域内直接值传递，无序列化
2. **旁路通讯零阻塞** — lock-free 实现，实时线程安全

## 跨进程：第三类旁路通讯

单进程旁路原语解决了节律域间的状态/事件共享，但不覆盖**跨进程**场景：

- 语言运行时隔离（Python GIL 不能阻塞硬实时控制）
- 故障隔离（视觉模块崩溃不带挂控制器）
- 在线热插拔（可视化 / 录制节点随时加入）
- 多机协同

Roplat 为此提供第三类旁路资源：**`ipc::*`**。节点侧代码契约与进程内一致 —— 只是「通道建立」由编译期静态改为运行时动态：

```rust
let (writer, _) = create_ipc_ring_buffer::<Pose>(&uri, Role::Publisher, rdv)?;
writer.unwrap().try_push(&pose);     // API 与 ring_buffer 完全一致
```

!!! info "身份三要素"
    跨进程无法共享 Rust 类型系统，需要字符串身份：

    ```text
    roplat-ipc://<namespace>/<endpoint>?msg=<schema_id>&v=<version>
    ```

    `schema_id` 由 `#[roplat_msg]` 宏在编译期对字段签名做 FNV-1a 哈希自动生成，握手阶段双侧校验。

### 对比矩阵

| 维度 | 进程内 (`triple_buffer` / `ring_buffer`) | 进程间 (`ipc::*`) |
|------|------------------------------------------|------------------|
| 绑定时机 | 编译期 `#[system]` 宏静态确定 | 运行时通过 rendezvous 动态发现 |
| 资源归属 | 系统图节点 | 独立 IPC 资源，不穿透系统图 |
| 类型安全 | Rust 类型系统 | `SchemaId` 指纹 + 握手校验 |
| 失败模式 | 几乎不可能 | `NotReady` / `PeerGone` / `SchemaMismatch` |
| 延迟 | 纳秒级 | TCP 后端约 100 μs |

详见 [通讯（贡献者向）§五](../Controbuction/5%20通讯.md#五进程间通讯ipc旁路通讯的跨进程版本) 与 [12 进程间通讯](../Controbuction/12%20进程间通讯.md)。
3. **类型安全** — 透明类型编译期检查，不透明类型通过 TypeBinding trait 约束
4. **跨语言透明** — 同一块内存，Rust/C++/Python 直接访问

## 下一步

- [快速开始](../QuickStart/00%20快速开始总览.md) — 动手实践
- [项目介绍](../Guide/01%20Introduction.md) — 回顾整体架构
