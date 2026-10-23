# 多设备与旁路

两台机械臂各有自己的控制节拍。如果把它们放进同一个节律，或者用图边连接两个控制域，慢的一台会拖住快的一台。roplat 的做法是：每台设备一个控制域，域之间没有图边，通过旁路交换**最新值**。

## 完整程序

主臂以 2 ms 的节拍走一条斜坡，并发布自己的位置；从臂以 3 ms 的节拍读取主臂的最新位置，保持 0.1 的偏移跟随。

<!-- roplat-example: sideband -->
```rust
use std::time::Duration;

use roplat::comm::{Latest, Publisher, Subscriber};
use roplat::rhythm::WithPeriod;
use roplat::{Lifecycle, Node, RoplatError, RoplatResult};

/// 单轴模拟机械臂。
#[derive(Default)]
struct Arm {
    position: f64,
}

impl Lifecycle for Arm {
    type Error = RoplatError;
}

/// 把机械臂移到设定点，输出到达后的位置。
struct Drive;

impl Lifecycle for Drive {
    type Error = RoplatError;
}

impl Node for Drive {
    type Resources = (Arm,);
    type Input = f64;
    type Output = f64;

    async fn process<'call>(&'call mut self, setpoint: f64, (arm,): (&'call mut Arm,)) -> f64 {
        arm.position = setpoint;
        arm.position
    }
}

/// 发布本设备的最新位置。
struct Share {
    board: Publisher<f64>,
}

impl Lifecycle for Share {
    type Error = RoplatError;
}

impl Node for Share {
    type Resources = ();
    type Input = f64;
    type Output = ();

    async fn process(&mut self, position: f64, _: ()) {
        self.board.publish(position);
    }
}

/// 读取对方的最新位置并加上偏移；还没有消息时保持 `hold`。
struct Mirror {
    board: Subscriber<f64>,
    offset: f64,
    hold: f64,
}

impl Lifecycle for Mirror {
    type Error = RoplatError;
}

impl Node for Mirror {
    type Resources = ();
    type Input = ();
    type Output = f64;

    async fn process(&mut self, (): (), _: ()) -> f64 {
        match self.board.latest() {
            Some(position) => position + self.offset,
            None => self.hold,
        }
    }
}

#[roplat::system]
async fn leader_and_follower() -> RoplatResult<(f64, f64)> {
    let board = Latest::<f64>::new(1);

    // 主臂：按自己的节拍走一条斜坡。
    let mut leader = Arm::default();
    let mut path = (1..=20)
        .map(|step| step as f64 * 0.02)
        .with_period(Duration::from_millis(2));
    let mut leader_drive = Drive;
    let mut share = Share {
        board: board.publisher(),
    };

    // 从臂：按另一个节拍跟随主臂的最新位置。
    let mut follower = Arm::default();
    let mut ticks = (0..40).with_period(Duration::from_millis(3));
    let mut mirror = Mirror {
        board: board.subscriber(0),
        offset: 0.1,
        hold: 0.0,
    };
    let mut follower_drive = Drive;

    // 两个控制域之间没有图边：它们是兄弟域，各自推进。
    path >> |setpoint| {
        &mut leader >> leader_drive.resources.0;
        setpoint >> leader_drive >> share;
    };

    ticks
        >> |_tick| {
            &mut follower >> follower_drive.resources.0;
            mirror >> follower_drive;
        };

    Ok((leader.position, follower.position))
}

#[tokio::main(flavor = "current_thread")]
async fn main() -> RoplatResult<()> {
    let (leader, follower) = leader_and_follower().await?;
    println!("leader {leader:.2}, follower {follower:.2}");
    Ok(())
}
```
<!-- /roplat-example -->

输出：

<!-- roplat-output: sideband -->
```text
leader 0.40, follower 0.50
```
<!-- /roplat-output -->

## 兄弟域

```rust
path >> |setpoint| {
    &mut leader >> leader_drive.resources.0;
    setpoint >> leader_drive >> share;
};

ticks >> |_tick| {
    &mut follower >> follower_drive.resources.0;
    mirror >> follower_drive;
};
```

两个节律域之间没有任何依赖，System 让它们各按自己的节拍并发推进，直到两者都结束。它们使用不同的设备，所以不需要排序。

## `Latest`：只要最新值

`Latest::<f64>::new(1)` 创建一个最新值通道，参数是订阅者数量。`publisher()` 取出唯一的发布端，`subscriber(i)` 取出第 i 个订阅端；每个端点只能取一次。端点在头段交给节点的构造函数，节点在 `process` 里发布和读取。

- 读者每次拿到读取时刻的最新版本，可能跳过中间版本。这是有意的：控制需要的是"现在"的状态，不是历史。
- 不同读者在不同时刻读取，不保证看到同一个版本，也没有全局快照。
- 还没有任何发布时，`latest()` 返回 `None`，节点自己决定怎么办（这里保持原位）。
- 旁路读写不产生图边，不影响调度。

需要逐条处理、不能丢失的数据（例如事件队列）用 `SpscQueue`；大块只读数据用 `FrameBuffer` / `SharedFrame`。选择方法见[通信](../concepts/communication.md)。

## 兄弟域怎样结束

每个域要有自己的结束条件，并考虑对方先结束的情况。本例两个域都是有限的：主臂 20 个周期，从臂 40 个周期，从臂最后一段时间读到的一直是主臂的最终位置，所以结果是确定的。

真实任务里，如果从臂只在"主臂报告完成"时结束，而主臂可能在报告之前就耗尽了周期，从臂会永远等下去。做法是让主臂在最后一个周期发布完成标志，或者给从臂加上自己的上限。

## 同周期的因果数据仍走图边

旁路只用于不同节拍、不同设备之间的信息交换。同一个周期里"先算这个、再用它算那个"的数据，仍然用图边连接，由 System 保证顺序和所有权。

下一篇：[事件与信号](events.md)。
