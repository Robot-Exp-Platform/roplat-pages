# Rhythm

Rhythm 决定一个执行域怎样推进：何时开始一个周期、把什么交给周期内的图、拿到图交回的值后做什么、何时结束整次运行。对机器人控制来说，最自然的节律往往由设备自己决定：周期开始时取得机器人状态，域内算完把指令交回，节律把指令发给设备。

## 四个边界

| 名称 | 方向 | 次数 |
|---|---|---|
| `Input` | 父图 → `drive` | 每次 drive 一份 |
| `Yield` | 节律 → 周期内的图 | 每个周期一份 |
| `Feed` | 周期内的图 → 节律 | 每个周期一份 |
| `Output` | `drive` → 父图 | 每次 drive 结束时一份 |

一次 **drive** 是节律的一次完整运行。Output 不必等于最后一次 Feed，节律可以返回统计、任务结果或任何其他值。父图依赖 Output 时，要等这次 drive 全部结束。

[节律的四个边界](../tutorial/rhythm-boundaries.md)用一个完整程序演示了这四种值。

## 在 System 里使用

```rust
rhythm >> { node; };                          // 不绑定 Yield，Feed 为 ()
rhythm >> |tick| { tick >> node; };           // 绑定每周期的 Yield
source >> rhythm >> |tick| { tick >> node; }; // source 的输出作为 Input
rhythm.output >> next;                        // 整次 drive 的 Output
```

- 周期域最后一个表达式没有分号时，它的值是本周期的 Feed；有分号时 Feed 为 `()`。
- 没有输入边时，`drive` 收到 `()` 作为 Input。
- `|(left, right)|` 可以解构 Yield；`|a, b|` 这样的多参数写法会被拒绝。

## 嵌套表示等待

父域的一个周期进入子节律后，要等子节律这次 drive 结束，才继续依赖它的后续节点。子节律不会自动变成后台任务；一个永不结束的子节律会让依赖它的父图停在那里。需要多个设备持续独立运行时，让它们成为兄弟域，经旁路交换信息，见[多设备与旁路](../tutorial/sideband.md)。

## 节律对象跨 drive 保留状态

同一个节律对象可以被多次 drive。迭代器节律记住剩余的位置，耗尽后再次 drive 不会重新开始；自定义节律保留自己的字段。框架不会在每次 drive 时重置节律；需要重新开始时，创建新对象或显式重置。

## 内置节律

| 构造 | 用途 |
|---|---|
| `iter.into_rhythm()` | 逐项运行，航点、任务步骤 |
| `iter.into_collect_rhythm()` | 逐项运行，Output 收集每个周期的 Feed |
| `iter.with_period(dt)` | 按固定间隔逐项运行 |
| `CountRhythm` / `create_count_rhythm(n)` | 运行 n 个周期 |
| `once()` | 每次 drive 一个周期，把一组节点包成可隔离、可 hard 的子域 |
| `retry(n)` | 重放一个步骤直到成功或用满 n 次 |
| `feedback(n, finished)` | 上一周期的 Feed 成为下一周期的 Yield，适合状态机 |
| `create_event_channel(cap)` | 每个外部事件一个周期 |
| `create_signal()` | 合并的通知，每次触发至多一个周期 |
| `ReplayFeedSource` | 重放录制的 Feed，见[录制与回放](replay.md) |

完整说明见[内置节点与节律](../reference/builtins.md)。设备的控制节律由驱动库提供。

## 实现自己的节律

```rust
fn drive<'call, N, F, Fut>(
    &'call mut self,
    nodes: N,
    op_domain: F,
    input: Self::Input,
    resources: <Self::Resources as ResourceSet>::Refs<'call>,
    context: ExecutionContext,
) -> impl Future<Output = (Execution<Self::Output>, N)> + Send
where
    N: Send,
    F: FnMut(N, Self::Yield, ExecutionContext) -> Fut + Send,
    Fut: Future<Output = (Execution<Self::Feed>, N)> + Send;
```

实现时可以写成 `async fn drive<N, F, Fut>(…)`；借用资源的节律带上 `'call` 生命周期，写法见[多层节律](../tutorial/layers.md)里的 `Control`。约定：

1. 每个周期开始前检查 `context.is_stopping()`，为真时返回 `Stopped`。
2. 调用 `op_domain(nodes, yield, context.clone())` 并完整等待；不要用超时或 `select!` 丢弃持有 `nodes` 的周期 Future。
3. 先取回 `nodes`，再处理这个周期的 `Execution`。
4. 周期失败或停止时请求停止，把结果和 `nodes` 一起返回。每条正常退出路径都要交回同一个 `nodes`。

`N` 由 System 宏规划，可能包含对象本体，也可能包含可变借用。节律不应假设它的类型或布局。

设备会话的收尾（例如最后一条保持指令）由节律或驱动自己完成；它不是对象的 `on_shutdown`，也不应被统一成"发零指令"或急停。

## hard 节律

`rhythm.hard()` 让每次 drive 在该节律自己的线程与运行时上执行，只能由拥有型域 `move |…| { … }` 进入。见 [hard 节律](../tutorial/hard.md)和[并发与放置](placement.md)。
