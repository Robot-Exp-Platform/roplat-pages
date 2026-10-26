# 分支、条件与重试

一个任务器依次处理操作员的指令：超出行程的目标直接拒绝，会撞上夹具的目标跳过，驱动偶尔报忙时重试，等待指令只是原地等一会儿。三种检查性质不同，roplat 里也用三种写法。

## 完整程序

<!-- roplat-example: branches -->
```rust
use std::ops::Range;
use std::time::Duration;

use roplat::rhythm::{IntoRhythm, retry};
use roplat::{Lifecycle, Node, RoplatError, RoplatResult};

/// 操作员下发的指令。
#[derive(Clone, Copy, Debug)]
enum Command {
    Goto(f64),
    Wait(Duration),
}

/// 单轴模拟机械臂。
#[derive(Default)]
struct Arm {
    position: f64,
}

impl Lifecycle for Arm {
    type Error = RoplatError;
}

/// 驱动报告的瞬时故障。
#[derive(Debug)]
enum Fault {
    Busy,
}

/// 运动节点：驱动前几次调用会报忙。
struct Motion {
    busy_calls: usize,
}

impl Lifecycle for Motion {
    type Error = RoplatError;
}

impl Node for Motion {
    type Resources = (Arm,);
    type Input = f64;
    type Output = Result<(), Fault>;

    async fn process<'call>(
        &'call mut self,
        target: f64,
        (arm,): (&'call mut Arm,),
    ) -> Self::Output {
        if self.busy_calls > 0 {
            self.busy_calls -= 1;
            return Err(Fault::Busy);
        }
        arm.position = target;
        Ok(())
    }
}

/// 碰撞检查：持有障碍物模型，所以由节点给出结论。
struct Clearance {
    keep_out: Range<f64>,
}

impl Lifecycle for Clearance {
    type Error = RoplatError;
}

impl Node for Clearance {
    type Resources = ();
    type Input = f64;
    type Output = bool;

    async fn process(&mut self, target: f64, _: ()) -> bool {
        !self.keep_out.contains(&target)
    }
}

/// 记录被拒绝的目标。
#[derive(Default)]
struct Refusals {
    targets: Vec<f64>,
}

impl Lifecycle for Refusals {
    type Error = RoplatError;
}

impl Node for Refusals {
    type Resources = ();
    type Input = f64;
    type Output = ();

    async fn process(&mut self, target: f64, _: ()) {
        self.targets.push(target);
    }
}

/// 统计运动结果：重试用尽后的失败也只是业务数据。
#[derive(Default)]
struct Outcomes {
    moved: usize,
    failed: usize,
}

impl Lifecycle for Outcomes {
    type Error = RoplatError;
}

impl Node for Outcomes {
    type Resources = ();
    type Input = Result<(), Fault>;
    type Output = ();

    async fn process(&mut self, result: Result<(), Fault>, _: ()) {
        match result {
            Ok(()) => self.moved += 1,
            Err(_) => self.failed += 1,
        }
    }
}

/// 原地等待，不使用机械臂。
struct Dwell;

impl Lifecycle for Dwell {
    type Error = RoplatError;
}

impl Node for Dwell {
    type Resources = ();
    type Input = Duration;
    type Output = ();

    async fn process(&mut self, time: Duration, _: ()) {
        tokio::time::sleep(time).await;
    }
}

struct Summary {
    position: f64,
    attempts: usize,
    moved: usize,
    failed: usize,
    out_of_reach: Vec<f64>,
    blocked: Vec<f64>,
}

fn within_limits(target: &f64) -> bool {
    (-1.0..=1.0).contains(target)
}

#[roplat::system]
async fn serve(commands: Vec<Command>) -> RoplatResult<Summary> {
    let mut arm = Arm::default();
    let mut tasks = commands.into_iter().into_rhythm();
    let mut clear = Clearance { keep_out: 0.4..0.6 };
    let mut attempt = retry::<f64, (), Fault>(3);
    let mut motion = Motion { busy_calls: 4 };
    let mut outcomes = Outcomes::default();
    let mut out_of_reach = Refusals::default();
    let mut blocked = Refusals::default();
    let mut dwell = Dwell;

    tasks
        >> |command| {
            match command {
                // 守卫只看指令本身：超出行程的目标直接拒绝。
                Command::Goto(target) if within_limits(&target) => {
                    target >> clear;
                    // 条件由节点算出，所以用图内 if。
                    if clear.output {
                        // 驱动报忙时只重放这一步，最多三次。
                        target
                            >> attempt
                            >> |(target, _try)| {
                                &mut arm >> motion.resources.0;
                                target >> motion;
                                motion
                            };
                        attempt >> outcomes;
                    } else {
                        target >> blocked;
                    }
                }
                Command::Goto(target) => {
                    target >> out_of_reach;
                }
                Command::Wait(time) => {
                    time >> dwell;
                }
            }
        };

    Ok(Summary {
        position: arm.position,
        attempts: attempt.attempts(),
        moved: outcomes.moved,
        failed: outcomes.failed,
        out_of_reach: out_of_reach.targets.clone(),
        blocked: blocked.targets.clone(),
    })
}

#[tokio::main(flavor = "current_thread")]
async fn main() -> RoplatResult<()> {
    let commands = vec![
        Command::Goto(0.8),
        Command::Goto(1.5),
        Command::Goto(0.5),
        Command::Wait(Duration::from_millis(10)),
        Command::Goto(-0.3),
    ];
    let summary = serve(commands).await?;
    println!(
        "moved {}, failed {}, attempts {}",
        summary.moved, summary.failed, summary.attempts
    );
    println!("out of reach: {:?}", summary.out_of_reach);
    println!("blocked: {:?}", summary.blocked);
    println!("position: {:.1}", summary.position);
    Ok(())
}
```
<!-- /roplat-example -->

输出：

<!-- roplat-output: branches -->
```text
moved 1, failed 1, attempts 5
out of reach: [1.5]
blocked: [0.5]
position: -0.3
```
<!-- /roplat-output -->

## 按检查的性质选写法

| 检查 | 依据 | 写法 |
|---|---|---|
| 目标是否在行程内 | 只看指令本身 | match **守卫** `Command::Goto(target) if within_limits(&target)` |
| 目标是否会碰撞 | 需要节点持有的障碍物模型 | 节点输出 `bool`，再用**图内 `if`** |
| 驱动报忙 | 瞬时故障，再试一次可能成功 | 用 **`retry(n)`** 包住这一步 |

### match 只执行选中的分支

```rust
tasks >> |command| {
    match command {
        Command::Goto(target) if within_limits(&target) => { ... }
        Command::Goto(target) => { target >> out_of_reach; }
        Command::Wait(time) => { time >> dwell; }
    }
};
```

被匹配的 `command` 是本周期的 Yield，模式绑定 `target`、`time` 是普通值，可以直接连到节点。每个分支也按"头段、图、尾段"组织。

**守卫**是原样保留的 Rust 表达式，只能读模式绑定和普通值。它不建立图依赖，所以不能读取节点的 `.output`，否则宏展开时报错。

### 图内 `if` 读取节点的结论

```rust
target >> clear;
if clear.output {
    ...
} else {
    target >> blocked;
}
```

条件是节点输出 `clear.output` 时，`if` 属于图：先运行 `clear`，再按结果只执行一个分支。图内 `if` 就是对 `bool` 的 match，可以写 `else if`、`if let`，也可以用 `let speed = if urgent.output { boost } else { cruise };` 汇合出一个结果。头段和尾段里只用普通值的 `if` 仍是普通 Rust。

### `retry` 只重放一个步骤

```rust
target >> attempt >> |(target, _try)| {
    &mut arm >> motion.resources.0;
    target >> motion;
    motion
};
attempt >> outcomes;
```

`retry::<f64, (), Fault>(3)` 是一个内置节律：Input 是目标，每个周期的 Yield 是 `(目标, 第几次尝试)`，周期的 Feed 是 `motion` 的 `Result<(), Fault>`。Feed 为 `Ok` 或用满 3 次时，本次 drive 结束，Output 是最后一次的 Feed。

三次都失败时，Output 仍是 `Err(Fault::Busy)` 这个**业务数据**：交给 `outcomes` 统计，任务器继续处理下一条指令。需要让失败结束整个任务时，改写成 `attempt?;`。

输出里 0.8 的三次尝试都遇到驱动报忙，记为失败；-0.3 第一次报忙、第二次成功。`attempt.attempts()` 是累计尝试次数，所以是 5。

安全相关的拒绝（限位、碰撞）不要重试；重试只用于瞬时故障。

## 同一实例只有一个调用位置

`motion`、`clear`、`attempt` 都只在一个分支里出现。同一个 match 的不同分支互斥，可以共用一个实例；但同一个实例不能既在外层调用、又在内层域调用，也不能在两个都会运行的域里各调用一次，否则编译报错并标出两处位置。需要两处使用同一种计算时，创建两个实例。

资源绑定也跟着调用位置走：`motion` 在 retry 的周期域里调用，`&mut arm >> motion.resources.0` 就写在那个域里。

## 尾段读取状态

尾段用 `outcomes.moved`、`out_of_reach.targets.clone()` 读取节点的状态。这些节点由本层创建，System 结束时还要调用它们的关闭钩子，所以尾段复制需要的数据，而不是把字段移走。

下一篇：[多层节律](layers.md)。
