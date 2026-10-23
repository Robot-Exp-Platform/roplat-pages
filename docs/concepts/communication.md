# 通信

同一个周期里"先算这个、再用它算那个"，和两台设备各按自己的节拍交换状态，是两种不同的需求。前者写图边，后者显式创建旁路。System 不会把图边自动换成队列或缓冲，也不会替跨域的状态交换决定语义。

## 先选数据关系

| 需求 | 用什么 | 语义 |
|---|---|---|
| 同一次计算依赖上一步的结果 | 图边 `sense >> plan >> act` | 类型化的值，由 System 安排顺序与所有权 |
| 独立的域读取对方的最新状态或指令 | `Latest<T>` | 可以跳过中间版本；每个读者有自己的三槽缓冲 |
| 按顺序处理每个成功入队的事件 | `SpscQueue<T>` | 单生产者单消费者；队列满时把值交回，由应用处理背压 |
| 外部线程发来的指令驱动任务 | 事件通道 / 信号 | 见[事件与信号](../tutorial/events.md) |
| 大块只读数据 | `FrameBuffer` → `seal()` → `SharedFrame` | 写入时独占，封存后共享，复制句柄不复制数据 |
| 不同进程或机器 | IPC | 独立的传输、发现与消息边界 |

旁路类型都在 `roplat::comm` 下。端点在头段创建，交给节点或节律的构造函数，在 `process` / `drive` 里读写；旁路读写不产生图边。

## Latest

```rust
let channel = roplat::comm::Latest::<u64>::new(1);   // 参数是订阅者数量
let mut publisher = channel.publisher();
let mut subscriber = channel.subscriber(0);
publisher.publish(7);
assert_eq!(subscriber.latest(), Some(&7));
```

- 每个端点只能从通道里取一次，取出后端点持有通道的生存期。发布端唯一、不可复制：不同节点要发布不同含义的信息时，各开一个通道。
- 读者在读取时刻拿到最新版本，可能跳过中间的发布；不同读者在不同时刻读取，没有全局快照。
- `latest()` 返回的借用不能跨过下一次读取；需要保留时复制或克隆。
- 端点不需要独占操作系统线程，可以由同一个异步任务里的节点持有。

完整的双臂例子见[多设备与旁路](../tutorial/sideband.md)。

## 共享大块数据

`FrameBuffer` 在 Rust 端分配并独占写入，`seal()` 消耗写权限，得到只读的 `SharedFrame`。克隆 `SharedFrame` 共享同一份数据，最后一个持有者释放时回收内存。仍有分配、引用计数和语言桥接的成本，不能称整条链路零开销。

## 跨进程：本机消息格式

typed IPC 的消息类型要求 `Copy + NativeMessage`。`#[roplat_msg]` 会生成相应的契约；手写的 `#[repr(C)]` 类型可以 `#[derive(roplat::NativeMessage)]`。引用、指针、`String`、`Vec` 这类类型不能通过这个契约。普通图边和进程内的旁路不要求 `NativeMessage`。

- 有填充的结构体逐字段编码并把间隙置零；无填充时可以直接借用原始字节。
- 这是本机内存布局和端序，不是跨架构的线上格式。
- **`NativeMessage` 不保证任意字节都是合法值。** 0.5 不校验 `bool` 等受限字段收到的位模式，非法值可能导致 Rust 未定义行为；长度检查不能替代这一点。不要把它用于接收不可信的外部字节。

IPC 是另一条字节传输路径，不能用进程内 `Latest` 的测试结果推断 IPC 的性能或类型安全。

## 外语对象

透明的跨语言消息以 Rust 定义的布局为准。外语创建的不透明对象（`OpaqueData`、`SendOpaque`、`SharedOpaque`）跨线程移动、共享或在指定线程析构，需要显式的契约；套一层 `Arc` 不会自动证明外部对象线程安全。见 [C++ 与 Python 节点](../integrate/languages.md)。
