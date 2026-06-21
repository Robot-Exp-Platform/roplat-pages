# 节律 Rhythm

Rhythm 决定一个执行域什么时候运行。它把“循环”从业务代码里拿出来，变成显式的调度抽象。

## 为什么需要 Rhythm

机器人程序里常见的执行方式包括：

- 每 10ms 跑一次控制器。
- 收到相机帧时跑一次检测。
- 测试时只执行 100 步。
- 离线读取一段轨迹。
- 按记录文件回放。

这些都不应该散落成手写循环。Roplat 用 Rhythm 统一表达。

## 内置节律

| Rhythm | Yield | 使用场景 |
|---|---|---|
| `SysTimer` | `EventMeta` | 固定周期任务 |
| `CountRhythm` | `usize` | 测试、示例、有限步仿真 |
| `EventRhythm<T>` | `T` | 外部事件触发 |
| `Iterator` | `Item` | 数据集、轨迹、离线输入 |
| `IterWithPeriod` | `Item` | 按周期播放迭代数据 |
| Replay rhythms | recorded frame | 确定性回放 |

## 周期任务

```rust
use std::time::Duration;

let mut timer = roplat::rhythm::SysTimer::new(Duration::from_millis(10));

timer >> {
    sensor >> controller >> motor;
};
```

`SysTimer` 的 yield 是 `EventMeta`，包含 timestamp、delta、jitter、sequence 等信息。如果图中需要 tick 元信息，用闭包形式：

```rust
timer >> |event| {
    event >> monitor.input;
};
```

## 计数任务

```rust
let (_, mut timer) = roplat::rhythm::create_count_rhythm(3);

timer >> {
    source >> sink;
};
```

`CountRhythm` 非常适合文档、测试和 benchmark，因为它不会引入真实时间的不稳定性。

## 事件任务

```rust
let (trigger, mut events) = roplat::rhythm::create_event_channel::<Frame>(16);

events >> |frame| {
    frame >> detector.input;
};
```

外部代码持有 `trigger`，调用 `trigger.fire(frame)` 后驱动一次事件域。

## 迭代任务

普通 `Iterator` 可以作为 Rhythm：

```rust
let mut samples = vec![1, 2, 3].into_iter();

samples >> |sample| {
    sample >> sink.input;
};
```

如果需要按周期播放：

```rust
use roplat::rhythm::WithPeriod;

let mut samples = trajectory.into_iter().with_period(Duration::from_millis(20));
```

## 什么时候实现自定义 Rhythm

只有在内置节律无法表达执行语义时才实现自定义 Rhythm，例如：

- 仿真器 step 和物理时间强绑定。
- 外部硬件 SDK 自带 blocking event loop。
- 需要特殊 feed-back 控制下一次 tick。

自定义 Rhythm 是框架扩展点，不是普通业务代码的默认选择。
