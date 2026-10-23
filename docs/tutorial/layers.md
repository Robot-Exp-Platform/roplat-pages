# 多层节律

机器人任务通常有两层节奏：任务层一段一段地给出目标，控制层在每一段里按设备的节拍逐周期计算。roplat 用节律嵌套表达这种结构，外层周期里进入内层节律的一次完整 drive。

## 完整程序

任务层依次给出三个目标；每一段里，设备控制节律 `Control` 借用机械臂运行到参考轨迹走完为止。

<!-- roplat-example: layers -->
```rust
use std::future::Future;

use roplat::rhythm::{IntoRhythm, Rhythm};
use roplat::{Completion, Execution, ExecutionContext, Lifecycle, Node, RoplatError, RoplatResult};

const DT: f64 = 0.01;

/// 单轴模拟机械臂。
#[derive(Default)]
struct Arm {
    position: f64,
}

impl Lifecycle for Arm {
    type Error = RoplatError;
}

/// 设备控制节律：每周期给出机械臂位置，收回 (速度, 是否结束)。
/// 真实项目里这类节律由驱动库提供；它借用机械臂，覆盖整次 drive。
#[derive(Default)]
struct Control {
    drives: usize,
}

impl Lifecycle for Control {
    type Error = RoplatError;
}

impl Rhythm for Control {
    type Resources = (Arm,);
    type Input = ();
    type Yield = f64;
    type Feed = (f64, bool);
    type Output = ();

    async fn drive<'call, N, F, Fut>(
        &'call mut self,
        mut nodes: N,
        mut cycle: F,
        (): (),
        (arm,): (&'call mut Arm,),
        context: ExecutionContext,
    ) -> (Execution<()>, N)
    where
        N: Send,
        F: FnMut(N, f64, ExecutionContext) -> Fut + Send,
        Fut: Future<Output = (Execution<(f64, bool)>, N)> + Send,
    {
        self.drives += 1;
        loop {
            if context.is_stopping() {
                return (Ok(Completion::Stopped), nodes);
            }
            let (execution, returned) = cycle(nodes, arm.position, context.clone()).await;
            nodes = returned;
            match execution {
                Ok(Completion::Completed((velocity, done))) => {
                    arm.position += velocity * DT;
                    if done {
                        return (Ok(Completion::Completed(())), nodes);
                    }
                }
                Ok(Completion::Stopped) => return (Ok(Completion::Stopped), nodes),
                Err(error) => {
                    context.request_stop();
                    return (Err(error), nodes);
                }
            }
        }
    }
}

/// 一段运动的参考轨迹：从本段第一次看到的位置匀速走到目标。
/// 每段新建，所以不需要手动复位。
struct Reference {
    goal: f64,
    steps: usize,
    step: usize,
    start: Option<f64>,
}

impl Reference {
    fn towards(goal: f64, steps: usize) -> Self {
        Self {
            goal,
            steps,
            step: 0,
            start: None,
        }
    }
}

impl Lifecycle for Reference {
    type Error = RoplatError;
}

impl Node for Reference {
    type Resources = ();
    type Input = f64;
    type Output = (f64, bool); // (设定点, 是否最后一步)

    async fn process(&mut self, position: f64, _: ()) -> (f64, bool) {
        let start = *self.start.get_or_insert(position);
        self.step += 1;
        let ratio = self.step as f64 / self.steps as f64;
        (start + (self.goal - start) * ratio, self.step == self.steps)
    }
}

/// 伺服律：跨段保留，统计发出的指令总数。
#[derive(Default)]
struct Servo {
    commands: usize,
}

impl Lifecycle for Servo {
    type Error = RoplatError;
}

impl Node for Servo {
    type Resources = ();
    type Input = (f64, (f64, bool));
    type Output = (f64, bool);

    async fn process(&mut self, (position, (setpoint, last)): Self::Input, _: ()) -> (f64, bool) {
        self.commands += 1;
        ((setpoint - position) / DT, last)
    }
}

#[roplat::system]
async fn visit(goals: Vec<f64>) -> RoplatResult<(f64, usize, usize)> {
    let mut arm = Arm::default();
    let mut tasks = goals.into_iter().into_rhythm();
    // 跨段保留：在外层创建。
    let mut control = Control::default();
    let mut servo = Servo::default();

    tasks
        >> |goal| {
            // 每段重新开始：在任务周期的头段创建。
            let mut reference = Reference::towards(goal, 10);

            &mut arm >> control.resources.0;
            control
                >> |position| {
                    position >> reference;
                    position >> servo.input.0;
                    reference >> servo.input.1;
                    servo
                };
        };

    Ok((arm.position, control.drives, servo.commands))
}

#[tokio::main(flavor = "current_thread")]
async fn main() -> RoplatResult<()> {
    let (position, drives, commands) = visit(vec![0.5, -0.2, 0.3]).await?;
    println!("control drives: {drives}, servo commands: {commands}");
    println!("final position: {position:.2}");
    Ok(())
}
```
<!-- /roplat-example -->

输出：

<!-- roplat-output: layers -->
```text
control drives: 3, servo commands: 30
final position: 0.30
```
<!-- /roplat-output -->

## 结构

```rust
tasks >> |goal| {
    let mut reference = Reference::towards(goal, 10);   // 每段新建

    &mut arm >> control.resources.0;                     // 机械臂借给控制节律
    control >> |position| {
        position >> reference;
        position >> servo.input.0;
        reference >> servo.input.1;
        servo                                            // 本周期的 Feed：(速度, 是否结束)
    };
};
```

- 外层 `tasks` 的每个周期是一段运动，Yield 是本段目标。
- 内层 `control` 是设备控制节律：每个周期给出机械臂位置，收回 `(速度, 是否结束)`，`done` 为真时结束这次 drive。外层周期要等这次 drive 结束才算完成。
- `control` 声明了 `type Resources = (Arm,)`，借用覆盖整次 drive；它的周期域里不能再把 `arm` 借给别的节点。

真实项目里，`Control` 这类设备节律由驱动库提供，应用只写周期内的算法。

## 对象放在哪一层

| 对象 | 创建位置 | 活多久 | 本例 |
|---|---|---|---|
| `control`、`servo` | System 头段 | 整次运行，跨段保留 | `control.drives` 累计到 3，`servo.commands` 累计到 30 |
| `reference` | 任务周期的头段 | 只属于这一段 | 每段从头开始，不需要手动复位 |
| `arm` | System 头段 | 整次运行 | 由本 System 启用与关闭 |

判断的问题只有一个：**这个状态要跨段保留吗？** 要保留的放外层；每段重新开始的放该段的头段。周期内创建的对象由该周期启用、在周期结束时关闭。

外层对象进入内层不会被重置，也不会被重复启用：`control` 在三段里是同一个对象，生命周期仍由创建它的 System 负责。

## Feed 一层层向上

内层周期域以 `servo` 结尾、没有分号，所以 `servo` 的输出是内层每周期的 Feed。外层周期域以 `};` 结尾，外层 Feed 是 `()`，与迭代器节律一致。

如果外层周期域直接以内层节律表达式结尾（没有分号），内层**整次 drive 的 Output** 就成为外层这个周期的 Feed。多层嵌套都按这条规则逐层传递。

## 什么时候不需要内层节律

只要"到达目标"、不需要逐周期参与计算时，用一个运动节点代替内层节律更简单：

```rust
tasks >> |goal| {
    &mut arm >> motion.resources.0;
    goal >> motion;
    motion?;
};
```

需要反馈控制、在线修正或与其他设备耦合时，用两层节律。

## 不要用嵌套模拟并行

外层依赖链里的子节律如果永不结束，外层就永远停在那里。两台设备需要各自持续运行时，不要把一台嵌套进另一台的周期，而是让它们成为互不依赖的兄弟域，见[多设备与旁路](sideband.md)。

下一篇：[失败、停止与收尾](stop-and-failure.md)。
