# 事件与信号

操作员界面、上位机或设备回调线程会在任意时刻发来指令。事件通道把这些指令变成一个节律：每条指令是一个周期。只需要知道"发生过"的通知（例如刷新面板）用信号，两次周期之间的多次触发合并成一次。

## 完整程序

操作员线程在 Tokio 运行时之外依次发送四条指令，每发一条就按一下刷新。System 里的指令域执行指令，面板域在收到刷新时显示最新位置。

<!-- roplat-example: events -->
```rust
use std::thread;

use roplat::comm::{Latest, Publisher, Subscriber};
use roplat::rhythm::{EventRhythm, SignalRhythm, create_event_channel, create_signal};
use roplat::{Lifecycle, Node, RoplatError, RoplatResult};

/// 操作员发来的指令。
#[derive(Clone, Copy, Debug)]
enum Command {
    Goto(f64),
    Home,
}

/// 单轴模拟机械臂。
#[derive(Default)]
struct Arm {
    position: f64,
}

impl Lifecycle for Arm {
    type Error = RoplatError;
}

/// 执行一条指令，并把机械臂的新位置发布给面板。
struct Execute {
    board: Publisher<f64>,
    done: usize,
}

impl Lifecycle for Execute {
    type Error = RoplatError;
}

impl Node for Execute {
    type Resources = (Arm,);
    type Input = Command;
    type Output = ();

    async fn process<'call>(&'call mut self, command: Command, (arm,): (&'call mut Arm,)) {
        arm.position = match command {
            Command::Goto(target) => target,
            Command::Home => 0.0,
        };
        self.done += 1;
        self.board.publish(arm.position);
    }
}

/// 操作面板：收到刷新信号时显示最新位置。
struct Panel {
    board: Subscriber<f64>,
    refreshes: usize,
}

impl Lifecycle for Panel {
    type Error = RoplatError;
}

impl Node for Panel {
    type Resources = ();
    type Input = ();
    type Output = ();

    async fn process(&mut self, (): (), _: ()) {
        self.refreshes += 1;
        let _shown = self.board.latest().copied();
    }
}

#[roplat::system]
async fn serve(
    mut commands: EventRhythm<Command>,
    mut refresh: SignalRhythm,
) -> RoplatResult<(f64, usize, usize)> {
    let board = Latest::<f64>::new(1);
    let mut arm = Arm::default();
    let mut execute = Execute {
        board: board.publisher(),
        done: 0,
    };
    let mut panel = Panel {
        board: board.subscriber(0),
        refreshes: 0,
    };

    // 每条指令是指令域的一个周期。
    commands
        >> |command| {
            &mut arm >> execute.resources.0;
            command >> execute;
        };

    // 刷新请求合并：两次周期之间的多次触发只算一次。
    refresh >> {
        panel;
    };

    Ok((arm.position, execute.done, panel.refreshes))
}

#[tokio::main(flavor = "current_thread")]
async fn main() -> RoplatResult<()> {
    let (orders, commands) = create_event_channel::<Command>(4);
    let (press, refresh) = create_signal();

    // 操作员线程在 Tokio 之外：用 fire_blocking 等待队列空位。
    let console = thread::spawn(move || {
        for command in [
            Command::Goto(0.4),
            Command::Goto(-0.2),
            Command::Home,
            Command::Goto(0.7),
        ] {
            orders.fire_blocking(command).expect("指令域已结束");
            press.fire();
        }
        // 线程结束时两个触发器被 drop，两个节律随之结束。
    });

    let (position, done, refreshes) = serve(commands, refresh).await?;
    console.join().expect("操作员线程 panic");
    assert!((1..=4).contains(&refreshes));
    println!("executed {done} commands, final position {position:.1}");
    Ok(())
}
```
<!-- /roplat-example -->

输出：

<!-- roplat-output: events -->
```text
executed 4 commands, final position 0.7
```
<!-- /roplat-output -->

## 事件通道

`create_event_channel::<Command>(4)` 返回一对 `(EventTrigger, EventRhythm)`，参数是队列容量。`EventRhythm` 交给 System 作为节律，每个事件的 Yield 就是指令本身：

```rust
commands >> |command| {
    &mut arm >> execute.resources.0;
    command >> execute;
};
```

触发器有三种发送方式，未能发送时都会把事件交回（`FireError::Full` 或 `FireError::Closed`）：

| 方法 | 是否等待 | 用在哪里 |
|---|---|---|
| `try_fire` | 不等待 | 任何地方，包括节点和周期内 |
| `fire_async().await` | 异步等待空位 | 异步代码里，前提是接收域能同时推进 |
| `fire_blocking` | 让线程睡眠等空位 | 只用于 Tokio 运行时之外的线程（界面、设备回调）；在节点、周期或 hard 节律里调用会 panic |

## 信号

`create_signal()` 返回 `(SignalTrigger, SignalRhythm)`。`SignalTrigger::fire` 不等待、不分配、不会 panic，触发器可以克隆。下一个周期开始前的多次触发合并成一个周期，周期不携带数据。本例按了四次刷新，面板可能只刷新一到四次，取决于两边的时序，所以程序只断言这个范围。

需要每个事件和它的内容时，用事件通道；只需要"有变化"时，用信号。

## 节律什么时候结束

只要还有一个触发器存活，事件节律和信号节律就会继续等待。所有触发器被 drop、队列取空之后，节律结束。本例中操作员线程结束时 `orders` 和 `press` 被 drop，两个域随之结束，System 正常返回。

!!! warning "不要把触发器交给同一 System 里的节点"
    节点要到 System 结束才会被 drop，而 System 又在等这个节律结束，于是永远不会结束。触发器应留在 System 之外（另一个线程、另一部分程序），发送完就 drop；需要中途结束整个 System 时，用[停止上下文](stop-and-failure.md#从外部停止)。

## 与图内分支组合

事件周期里可以照常使用 match、守卫、图内 `if` 和 `retry`，写法与[分支、条件与重试](branches.md)相同：指令进入一个周期，周期里按指令类型分支、检查、执行。

下一篇：[hard 节律](hard.md)。
