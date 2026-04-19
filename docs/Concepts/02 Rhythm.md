# Rhythm — 节律源

Rhythm 是 Roplat 的时间抽象——它回答"**什么时候执行**"这个问题。

如果把 Node 比作电子元件，那 Rhythm 就是给它们供电的**电源**。没有 Rhythm 驱动，Node 不会自己执行。

## Rhythm Trait

```rust
pub trait Rhythm {
    type Yield: Send;       // 节律源给节点的输入数据
    type Feed;              // 节点返回给节律的反馈
    type Output;            // drive 完成后的最终结果
    type Error: Into<RoplatError> + Debug;

    /// 驱动节点组执行
    fn drive<N, F, Fut>(
        &mut self,
        nodes: N,
        op_domain: F,
    ) -> impl Future<Output = Self::Output> + Send
    where
        N: Send,
        F: FnMut(N, Self::Yield) -> Fut + Send,
        Fut: Future<Output = (Self::Feed, N)> + Send;
}
```

### 理解 drive 的签名

`drive` 方法的核心思想是**值传递**：

1. `nodes: N` — 将节点元组的**所有权**移入 drive
2. 每个 tick，`op_domain` 闭包接收节点 + Yield 数据，返回 `(Feed, nodes)`
3. 节点通过返回值**移回**给 drive，供下一个 tick 使用

这种设计的优势：

- **零堆分配**：不需要 `Box<dyn Future>`，每 tick 没有内存分配
- **编译器优化**：节点元组通常是小型指针集合，移入/移出被优化为寄存器操作
- **Send 安全**：值传递消除了引用的生命周期问题，`Fut` 可以安全地标记为 `Send`

!!! note "在 System DSL 中控制 Feed"
    system 宏利用 Rust 的分号语义自动推导 Feed 类型：块中最后一条链**无分号**时，其输出作为 Feed；**有分号**时，Feed 为 `()`。详见 [系统 System — 分号语义与 Feed 类型](03%20System.md#分号语义与-feed-类型)。

## 四种内置节律源

### 1. SysTimer — 系统定时器

固定周期执行，最常用的节律源。

```rust
let timer = SysTimer::new(Duration::from_millis(10)); // 100Hz
```

每 tick 产出 `EventMeta`：

```rust
pub struct EventMeta {
    pub timestamp: Instant,  // 物理时间戳（单调递增）
    pub delta: Duration,     // 逻辑周期（控制算法应使用的 dt）
    pub jitter: Duration,    // 物理抖动（监控用）
    pub sequence: u64,       // 序号（丢帧检测）
}
```

!!! tip "delta vs timestamp"
    控制算法应使用 `delta`（逻辑周期），而非自己计算时间差。`delta` 是恒定的设定值，不受系统调度抖动影响。`jitter` 字段提供实际抖动信息用于监控。

### 2. CountRhythm — 计数节律

执行固定次数后结束，适合初始化序列或有限任务：

```rust
let (handle, rhythm) = create_count_rhythm(100); // 执行 100 次

// handle 可以在运行时动态修改次数
handle.set_times(200);
```

### 3. EventRhythm — 事件触发

由外部事件驱动，触发时机不可预测。典型场景：传感器帧到达、硬件中断。

```rust
let (trigger, rhythm) = create_event_channel::<SensorFrame>(16);

// 外部线程（如传感器驱动）调用 trigger.fire() 触发执行
trigger.fire(new_frame);
```

核心循环等待 `tokio::mpsc` 通道消息，每收到一条就执行一帧。

!!! warning "EventRhythm 与回放"
    EventRhythm 的触发时机和 Yield 数据完全由外部决定。在录制/重放场景中，必须同时记录每帧的 Yield 数据和时间戳。详见 RFC 0018。

### 4. Iterator 适配器

任何实现了 `Iterator` 的类型都自动实现 `Rhythm`：

```rust
let data = vec![1.0, 2.0, 3.0, 4.0, 5.0];
// data.into_iter() 即可作为节律源，全速驱动
```

适用场景：

- 离线仿真 / 批处理
- 算法测试
- 数据回放

!!! note "Iterator 节律的限制"
    Iterator 是开环的——它不处理 Feed（反馈）。如果你的节点需要根据上一帧的输出调整下一帧的输入（闭环控制），请使用 `SysTimer` 或 `EventRhythm`。

## 节律域

在一个 system 中，可以有多个节律源同时运行，每个节律源驱动一组节点——这称为一个**节律域**：

```rust
#[roplat::system]
async fn robot() {
    let mut sensor = IMU::new();
    let mut ctrl   = Controller::new();
    let mut camera = Camera::new();
    let mut detect = Detector::new();

    // 域 1：高频控制回路
    timer_1khz >> {
        sensor >> ctrl;
    };

    // 域 2：低频视觉处理
    timer_30hz >> {
        camera >> detect;
    };
}
```

不同域之间的节点通过**旁路通讯**（channel）交换数据，在 system DSL 中会自动插入通道。

## 生命周期管理

Rhythm 管理其域内节点的完整生命周期：

```text
init()        ─→  on_init() 被调用（所有节点）
                      │
drive()       ─→  tick 1: op_domain(nodes, yield)
                  tick 2: op_domain(nodes, yield)
                  tick N: op_domain(nodes, yield)
                      │
shutdown()    ─→  on_shutdown() 被调用（所有节点）
```

## 性能特征

| 节律源 | 每 tick 开销 | 堆分配 | 适用频率 |
|:------|:-----------|:------|:--------|
| SysTimer | ~1μs（sleep + wake） | 0 | 1Hz - 10kHz |
| CountRhythm | ~0.1μs | 0 | 不限 |
| EventRhythm | ~1μs（channel recv） | 0 | 取决于事件源 |
| Iterator | ~0ns | 0 | 全速（CPU bound） |

## 下一步

- [System 系统](03%20System.md) — 了解如何将节点和节律组装为完整系统
- [通讯模型](04%20Comm.md) — 了解节律域之间如何交换数据
