# Replay — 确定性录制与回放

Replay 模块解决的问题是：**如何将一次真实运行完整记录下来，之后可以确定性地重放？**

这对于机器人系统至关重要——传感器数据不可重来，bug 复现需要完全相同的输入序列，算法迭代需要在相同数据上对比。

## 核心思想：录制边界 = Rhythm 的 drive 接口

Roplat 不在 Node 层录制，而是在 **Rhythm 的 `drive()` 方法**中拦截两个接口点：

```text
Rhythm                    Node 域
  │                         │
  │── Yield ──────────────▶ │  (输入：传感器数据、时间戳……)
  │                         │
  │◀── Feed ──────────────  │  (输出：控制指令、状态反馈……)
  │                         │
```

- **Yield**：节律源每 tick 给节点的输入数据
- **Feed**：节点处理后返回给节律的输出数据

录制 = 在这两个点透明地序列化每帧 `(Yield, Feed, timestamp)`。
回放 = 用录制的 Yield 序列替代真实输入，驱动节点执行。

!!! tip "为什么不在 Node 层录制？"
    Node 的 `process()` 签名会随算法迭代频繁变化，而 Rhythm 的 `drive()` 接口是稳定的。在 Rhythm 层录制意味着**节点完全不知道自己在被录制或回放**，零侵入。

## 录制：RecordingRhythm

将任何现有的 Rhythm 包一层 `RecordingRhythm`，即可开始录制：

```rust
use roplat::rhythm::replay::*;
use std::sync::{Arc, atomic::AtomicU64};

// 1. 创建共享的帧写入器
let writer = FrameWriter::create("session.rlog", &[
    RhythmMeta {
        rhythm_id: 0,
        name: "control".into(),
        yield_type_name: "EventMeta".into(),
        feed_type_name: "ControlOutput".into(),
    },
]).unwrap();

let global_seq = Arc::new(AtomicU64::new(0));

// 2. 包装真实节律——节点无感知
let timer = SysTimer::new(Duration::from_millis(10));
let mut recording = RecordingRhythm::new(timer, 0, writer.clone(), global_seq);

// 3. 像普通 Rhythm 一样 drive
recording.drive(nodes, |nodes, event_meta| async move {
    // 节点逻辑完全不变
    let output = controller.process(event_meta).await;
    (output, nodes)
}).await;

// 4. 录制完成，flush 写入
writer.flush();
```

**不录制 = 不包装，零开销。** RecordingRhythm 的序列化成本约 1–10μs/帧，对 ≤10kHz 控制循环影响极小。

## 回放：ReplayRhythm

用录制的帧数据替代真实节律源：

```rust
use roplat::rhythm::replay::*;

// 1. 打开录制文件
let rlog = RlogReader::open("session.rlog").unwrap();
let frames = rlog.frames_for(0); // 获取域 0 的帧

// 2. 创建回放节律
let mut replay = ReplayRhythm::<EventMeta, ControlOutput>::new(
    frames,
    ReplayMode::Full { tolerance: FeedCheck::Exact },
    ReplayTiming::AsFast,
);

// 3. 驱动节点——与录制时完全相同的代码
let mismatches = replay.drive(nodes, |nodes, event_meta| async move {
    let output = controller.process(event_meta).await;
    (output, nodes)
}).await;

// 4. 检查是否有 Feed 不匹配
if mismatches.is_empty() {
    println!("回放通过：节点输出与录制完全一致");
}
```

## 三种回放模式

| 模式 | 节点执行？ | Feed 校验？ | 典型用途 |
|:-----|:----------|:-----------|:--------|
| **Full** | 是 | 是 | 回归测试：验证算法修改后输出不变 |
| **InputOnly** | 是 | 否 | 算法迭代：用相同输入测试新算法 |
| **OutputOnly** | 否 | — | 数据供给：给下游 live 域提供录制数据 |

### Full 模式的 Feed 校验

Full 模式在每帧结束后比较实际 Feed 与录制 Feed：

```rust
// 严格字节级比较
ReplayMode::Full { tolerance: FeedCheck::Exact }

// 浮点容差比较（适用于浮点运算的微小差异）
ReplayMode::Full { tolerance: FeedCheck::Tolerance(1e-6) }

// 不校验（仅录制 Yield，忽略 Feed）
ReplayMode::Full { tolerance: FeedCheck::None }
```

!!! tip "什么时候用 Tolerance？"
    如果你的节点包含浮点运算（PID、滤波器、矩阵运算），同一平台上结果通常是 bit-exact 的。但跨编译器版本或优化级别时可能出现微小差异，此时使用 `Tolerance(1e-9)` 即可。

## 时序控制

回放时如何控制时间推进：

| 策略 | 行为 | 用途 |
|:-----|:-----|:-----|
| `AsFast` | 全速执行，不等待 | 单元测试、CI |
| `Realtime` | 按录制时的帧间隔 sleep | 与 live 域混合运行 |
| `Scaled(f)` | 倍速/慢速（`f=2.0` 双倍速） | 调试慢放、加速验证 |

## 多域回放：ReplayOrchestrator

当系统有多个节律域时，需要按录制时的全局序号交错执行：

```rust
let rlog = RlogReader::open("session.rlog").unwrap();
let mut orch = ReplayOrchestrator::from_rlog(&rlog);

// 为每个域创建 ReplayRhythm + TurnToken
for rid in orch.rhythm_ids() {
    let frames = orch.take_frames(rid);
    let token = orch.turn_token(rid);

    tokio::spawn(async move {
        let mut replay = ReplayRhythm::<Y, D>::new(
            frames,
            ReplayMode::InputOnly,
            ReplayTiming::AsFast,
        );
        // token 保证各域按全局序号交替执行
        // ...
    });
}
```

`TurnToken` 的工作方式：

1. 每帧执行前调用 `token.wait_turn(expected_seq).await`
2. 如果当前全局序号还没轮到自己，等待
3. 执行完成后调用 `token.advance()` 推进全局序号并唤醒其他域

## .rlog 文件格式

录制文件使用 JSON-lines 格式（每行一条 JSON）：

```text
{"magic":"RLOG","version":2,"rhythms":[{"rhythm_id":0,"name":"control",...}]}
{"global_seq":0,"rhythm_id":0,"timestamp_ns":1000000,"yield_data":[...],"feed_data":[...]}
{"global_seq":1,"rhythm_id":0,"timestamp_ns":2000000,"yield_data":[...],"feed_data":[...]}
...
```

优势：

- **可读性**：`head -5 session.rlog` 直接查看
- **崩溃安全**：逐行追加，即使进程崩溃也不损坏已有数据
- **流式处理**：不需要加载整个文件到内存

Yield 和 Feed 数据使用 bincode 序列化为字节数组，嵌入 JSON。

## 什么时候录制，什么时候不录制

| 场景 | 建议 |
|:-----|:-----|
| 真实硬件测试 | **必须录制** — 传感器数据不可重来 |
| CI 回归测试 | 录制一次，多次回放 |
| 日常开发调试 | 可选 — 录制开销小 |
| 高频大数据（相机流） | 选择性录制 — 只录关键域 |
| 性能基准测试 | **不录制** — 避免 IO 引入噪声 |

!!! warning "类型要求"
    录制要求 Yield 和 Feed 类型实现 `Serialize + DeserializeOwned`。使用 `#[roplat_msg]` 宏定义的消息类型会自动派生这些 trait。
