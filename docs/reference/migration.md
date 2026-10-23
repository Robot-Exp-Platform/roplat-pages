# 从 0.4 迁移

roplat 0.5 相对 0.4 是破坏性更新：资源改为独立的借用通道，`#[hard]` 改为 hard 节律，事件触发器的发送方式拆分，同一实例跨作用域只能在一处调用。crates.io 上更早的 0.2 系列没有这些接口。9 个核心包（`roplat`、`roplat_macros`、`roplat_system`、`roplat_launch`、`roplat_build`、`roplat_cpp`、`roplat_cpp_msg`、`roplat_py`、`cargo-roplat`）统一为 0.5.0。

## 对照表

| 0.4 写法 | 0.5 写法 |
|---|---|
| `fn process(&mut self, input)`，设备放在 Input/Output 里归还 | `type Resources = (Arm,)`，`process(&mut self, input, (arm,): (&mut Arm,))`；图中 `&mut arm >> node.resources.0` |
| `ResourceSlot`、`reclaim_input`、资源返回边 | 删除；借用在调用结束时自动结束 |
| 依赖绑定的书写顺序排列同一资源的使用 | 补 `a >> b.trigger;` |
| `#[hard] let mut node = …;` | `let mut step = once::<I, O>().hard();`，以 `move |x| { … }` 进入 |
| `trigger.fire(event)` | 节点内 `try_fire(event)` 或 `fire_async(event).await`；外部线程 `fire_blocking(event)`；只需通知时用 `create_signal()` |
| 尾段读取内层节点 `Ok(reach.output)` | 让 `reach` 作为域的尾表达式，读 `task.output` |
| 外层绑定资源、分支内调用 | 在调用所在的作用域绑定资源 |
| 不借用资源的节点 | 也要写 `type Resources = ();`，`process` 增加第三个参数 `_: ()` |
| 自定义 `Rhythm::drive` | 在 `input` 与 `context` 之间增加 `resources` 参数 |

## 新增

- 图内 `if`（含 `else if`、`if let`、`let x = if …`）、match 守卫、闭包节点 `roplat::node::map`。
- 任务节律 `retry(n)`、`feedback(n, finished)`，以及 `once()`。
- `create_signal()`：不等待、不分配的合并通知。
- `cargo roplat graph`：画出书写的图与规约后的调度树。

## 行为变化

- 只有根作用域的独立部分会 `tokio::spawn`；节律周期与 match 分支里的并发一律同任务 join。
- 调度与语句书写顺序无关；图中有环和会造成通道死锁的结构改为带位置的编译诊断。
- 资源顺序和被其他路径蕴含的数据边不再把串并结构的图切开。
- 嵌套节律每个调用位置复用一个停止作用域，周期内的嵌套域每周期不再分配；`ExecutionContext` 由 8 字节变为 16 字节。上一次 drive 的句柄不能停止新的 drive。
- `EventTrigger::fire` 删除：它在任何 Tokio 运行时内都会 panic。

## 迁移步骤

1. 把依赖改为 `roplat = "0.5.0"`，所有 roplat 系列包使用同一版本。
2. 给每个 `Node` 和 `Rhythm` 加上 `type Resources`，补齐 `process` / `drive` 的资源参数。
3. 把设备从 Input/Output 里拿出来，改成 `.resources.N` 借用；删除归还相关的代码。
4. 按编译诊断补 `.trigger` 边、移动资源绑定、拆分重复的调用位置。
5. `#[hard]` 改为 hard 节律，事件发送改为新方法。
6. 运行有限的无设备版本，在调用方断言结果、调用次数和保留的状态。
