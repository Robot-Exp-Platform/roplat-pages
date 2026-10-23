# 内置节点与节律

## 内置节律

都在 `roplat::rhythm` 下。

| 构造 | 每周期 Yield | drive 何时结束，Output 是什么 | 典型用途 |
|---|---|---|---|
| `iter.into_rhythm()`（`IntoRhythm`） | 迭代器的下一项 | 迭代器耗尽；Output `()`。位置跨 drive 保留 | 航点、任务步骤 |
| `iter.into_collect_rhythm()` | 同上 | 同上；Output 是本次各周期 Feed 的 `Vec` | 逐段收集结果 |
| `iter.with_period(dt)`（`WithPeriod`） | 下一项，按 `dt` 定时 | 迭代器耗尽；Output `()` | 定频采样、脚本化输入 |
| `CountRhythm::new(n)` / `create_count_rhythm(n)` | 计数 | 跑满 n 个周期；`CountHandle` 可动态修改 n | 有限次循环 |
| `SysTimer::new(interval)` | `EventMeta`：时间戳、逻辑周期 `dt`、抖动、序号、是否超时唤醒 | 不会自行结束，靠停止上下文结束 | 长期运行的软件定时循环 |
| `once::<I, F>()` | Input 本身 | 一个周期；Output 是该周期的 Feed | 把一组节点包成可隔离、可 hard 的子域 |
| `retry::<I, O, E>(n)` | `(input, attempt)`，attempt 从 0 开始 | Feed 为 `Ok` 或用满 n 次；Output 是最后一次 Feed（`Result<O, E>`）。`attempts()` 是累计次数 | 重试一个步骤 |
| `feedback(n, finished)` | 首周期为 Input，之后为上一周期 Feed | `finished(&feed)` 成立或用满 n 个周期；Output 是最后一次 Feed | 状态机 |
| `create_event_channel::<T>(cap)` | 每个事件一份 | 所有触发器被 drop 且队列取空 | 操作员指令、外部请求 |
| `create_signal()` | `()` | 所有触发器被 drop 且没有待处理的触发 | 刷新、唤醒 |
| `ReplayFeedSource<D>`、`ReplayRhythm<Y, D>` | 录制的 Feed / Yield | 记录播放完毕 | 见[录制与回放](../concepts/replay.md) |

- `once`、`retry`、`feedback`、事件和信号节律在周期停止或失败时结束 drive 并请求停止。
- `once()` 每次 drive 都运行一次；不要用会耗尽的 `(0..1).into_rhythm()` 代替它。
- `retry` 全部失败时 Output 仍是业务数据，`retry.output?` 才升级为错误。
- 任何节律都可以 `.hard()`（`IntoHard`），见 [hard 节律](../tutorial/hard.md)；`.name("…")` 给 hard 线程命名。

### 事件与信号的发送

| 方法 | 是否等待 | 适用 |
|---|---|---|
| `EventTrigger::try_fire` | 不等待 | 任何上下文 |
| `EventTrigger::fire_async().await` | 异步等待空位 | 异步代码，接收域能同时推进时 |
| `EventTrigger::fire_blocking` | 线程睡眠等待空位 | 只用于 Tokio 运行时之外的线程 |
| `SignalTrigger::fire` | 不等待、不分配 | 任何上下文；两次周期之间的触发合并 |

未能发送时返回 `FireError::Full` 或 `FireError::Closed`，并交回事件。

## 内置节点

都在 `roplat::node` 下，适合示例、测试和简单的数据处理。

| 模块 | 节点 |
|---|---|
| `node::map` | 闭包节点 `map(|x| …)` |
| `node::arithmetic` | `OpAdd`、`OpSub`、`OpMul`、`OpDiv`、`OpRem`、`OpNeg`、`OpAbs`、`OpMax`、`OpMin`、`OpPow`、`OpSqrt` |
| `node::logic` | `LogicAnd`、`LogicOr`、`LogicXor`、`LogicNot`、`LogicNand`、`LogicNor`；`Equal`、`NotEqual`、`Greater`、`GreaterEqual`、`Less`、`LessEqual`；按位运算与移位 |
| `node::filter` | `MovingAverage`、`ExponentialMovingAverage`、`MedianFilter`、`RateLimiter`、`DeadzoneFilter`、`LowPassFilter` |
| `node::io` | `stdout_writer`、`stderr_writer`、`stdout_display_writer`、`stdout_debug_writer` 等写入节点 |

构造参数与输入输出类型见 [docs.rs](https://docs.rs/roplat/0.5.0/roplat/node/index.html)。
