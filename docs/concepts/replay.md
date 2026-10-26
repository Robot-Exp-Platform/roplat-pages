# 录制与回放

roplat 可以录制一个节律每个成功周期的 Yield 和 Feed，之后用两种方式使用这份记录：把录制的输入重新喂给同一段图，并比较新算出的 Feed；或者把录制的 Feed 作为另一段图的输入。相关类型在 `roplat::rhythm::replay` 下。

## 录制了什么

每个**成功**周期的 Yield、Feed、开始时间和完成顺序。以下内容不在记录里：

- 失败或停止的周期，整次 drive 的 Input 和 Output；
- 对象的内部状态、旁路读取到的值和读取顺序；
- 对外部世界的副作用。

所以回放不是自动的确定性重现，也不会隔离副作用：回放时运行的仍是真实的应用代码。

## 三种用法

| 用法 | 新图每周期收到 | 新图交回 | 整次 drive 的 Output |
|---|---|---|---|
| `ReplayRhythm` + `ReplayMode::InputOnly` | 录制的 Yield | 当前计算的 Feed | 空差异列表 |
| `ReplayRhythm` + 比较器 | 录制的 Yield | 当前计算的 Feed | 与录制 Feed 的差异列表 |
| `ReplayFeedSource` | 录制的 Feed | `()` | `FeedReplayReport`（完成的帧数） |

```rust
let player = SessionPlayer::open("session.rlog")?;
let mut source = player.replay_feed_source::<Command>(7, ReplayTiming::AsFast);
// 在 System 的图里：
source >> |command| command >> consumer;
source.output >> report;
```

录制由 `SessionRecorder` 完成，它包装一个节律并记录每个成功周期。

## 比较

默认的精确比较按编码后的字节判断，比较的是编码而不是业务含义（例如正零和负零会被判为不同）。浮点数据用类型化的比较器：

```rust
let replay = player
    .replay_rhythm::<State, [f64; 6]>(7, ReplayMode::InputOnly, ReplayTiming::AsFast)
    .with_comparator(FloatTolerance::new(1e-6, 1e-4)?);
```

`with_comparator` 会把回放切换为完整的类型化校验：把录制的 Feed 解码成真实类型后再比较。`FloatTolerance` 支持 `f32`、`f64`、数组和 `Vec`，判定规则为 `|期望 - 实际| <= 绝对容差 + 相对容差 × max(|期望|, |实际|)`；NaN 总是不匹配。任意业务类型也可以传入闭包作为比较器。发现差异只记录，不会自动停止。

## 注意

- 回放日志使用 serde/bincode 编码，与 IPC 的本机内存格式不同，两种字节不能互换。
- `ReplayMode::OutputOnly` 和 `FeedCheck::Tolerance` 不是可用的执行入口，会在 drive 开始前报错。
- 录制回放的 API 还在演进，以 [docs.rs](https://docs.rs/roplat/0.5.0/roplat/rhythm/replay/index.html) 上的签名为准。
