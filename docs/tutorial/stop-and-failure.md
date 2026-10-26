# 失败、停止与收尾

程序运行中会遇到三类不同的事：节点算出了"做不到"的结果，某个执行域失败了，或者外部要求整个程序停下来。roplat 把它们分开表达，并保证在合作式退出时等待在途的工作、归还对象、执行收尾。

## 完整程序

第一个 System 依次执行三段运动，中间一段超出行程而失败，父层记录下来后继续下一段。第二个 System 是一个永不自行结束的监视循环，由外部在 30 ms 后请求停止。

<!-- roplat-example: stop-and-failure -->
```rust
use std::time::Duration;

use roplat::rhythm::{IntoRhythm, WithPeriod, once};
use roplat::{Completion, Execution, ExecutionContext, Lifecycle, Node, RoplatError, RoplatResult};

/// 单轴模拟机械臂。
#[derive(Default)]
struct Arm {
    position: f64,
}

impl Lifecycle for Arm {
    type Error = RoplatError;
}

/// 运动节点：超出行程时返回业务错误。
struct Motion;

impl Lifecycle for Motion {
    type Error = RoplatError;
}

impl Node for Motion {
    type Resources = (Arm,);
    type Input = f64;
    type Output = Result<(), RoplatError>;

    async fn process<'call>(&'call mut self, goal: f64, (arm,): (&'call mut Arm,)) -> Self::Output {
        if goal.abs() > 1.0 {
            return Err(RoplatError::NodeProcessing(format!("目标 {goal} 超出行程")));
        }
        arm.position = goal;
        Ok(())
    }
}

/// 父层显式处理每一段的完整执行结果。
#[derive(Default)]
struct Report {
    lines: Vec<String>,
}

impl Lifecycle for Report {
    type Error = RoplatError;
}

impl Node for Report {
    type Resources = ();
    type Input = (f64, Execution<()>);
    type Output = ();

    async fn process(&mut self, (goal, outcome): Self::Input, _: ()) {
        let line = match outcome {
            Ok(Completion::Completed(())) => format!("segment {goal}: completed"),
            Ok(Completion::Stopped) => format!("segment {goal}: stopped"),
            Err(error) => format!("segment {goal}: failed ({error})"),
        };
        self.lines.push(line);
    }
}

/// 一段失败不影响后面的段：每段是一个 once 子域，父层读它的 .outcome。
#[roplat::system]
async fn segments(goals: Vec<f64>) -> RoplatResult<Vec<String>> {
    let mut arm = Arm::default();
    let mut tasks = goals.into_iter().into_rhythm();
    let mut segment = once::<f64, ()>();
    let mut motion = Motion;
    let mut report = Report::default();

    tasks
        >> |goal| {
            goal >> segment
                >> |goal| {
                    &mut arm >> motion.resources.0;
                    goal >> motion;
                    motion?
                };
            goal >> report.input.0;
            segment.outcome >> report.input.1;
        };

    Ok(report.lines.clone())
}

/// 每次采样计一次数。
struct Sampler {
    samples: usize,
}

impl Lifecycle for Sampler {
    type Error = RoplatError;
}

impl Node for Sampler {
    type Resources = ();
    type Input = u64;
    type Output = ();

    async fn process(&mut self, _tick: u64, _: ()) {
        self.samples += 1;
    }
}

/// 日志节点：由 System 创建，停止时也会被关闭。
struct Log;

impl Lifecycle for Log {
    type Error = RoplatError;

    async fn on_shutdown(&mut self) -> RoplatResult<()> {
        println!("log closed");
        Ok(())
    }
}

impl Node for Log {
    type Resources = ();
    type Input = ();
    type Output = ();

    async fn process(&mut self, (): (), _: ()) {}
}

/// 永不自行结束的监视循环，由外部通过上下文停止。
#[roplat::system(context = context)]
async fn monitor(context: ExecutionContext, sampler: &mut Sampler) -> Execution<()> {
    let mut ticks = (0..).with_period(Duration::from_millis(2));
    let mut log = Log;

    ticks
        >> |tick| {
            tick >> sampler;
            log;
        };

    Ok(Completion::Completed(()))
}

#[tokio::main(flavor = "current_thread")]
async fn main() -> RoplatResult<()> {
    for line in segments(vec![0.5, 3.0, -0.5]).await? {
        println!("{line}");
    }

    let context = ExecutionContext::new();
    let stopper = context.clone();
    tokio::spawn(async move {
        tokio::time::sleep(Duration::from_millis(30)).await;
        stopper.request_stop();
    });
    let mut sampler = Sampler { samples: 0 };
    let result = monitor(context, &mut sampler).await;
    assert!(sampler.samples > 0);
    match result {
        Ok(Completion::Stopped) => println!("monitor: stopped"),
        other => println!("monitor: unexpected {other:?}"),
    }
    Ok(())
}
```
<!-- /roplat-example -->

输出：

<!-- roplat-output: stop-and-failure -->
```text
segment 0.5: completed
segment 3: failed (节点处理错误: 目标 3 超出行程)
segment -0.5: completed
log closed
monitor: stopped
```
<!-- /roplat-output -->

## 三层含义

| 层次 | 例子 | 表达方式 |
|---|---|---|
| 业务结果 | 运动节点返回 `Err`，"目标超出行程" | 节点 Output 里的 `Result`，默认只是数据 |
| 执行失败 | 用 `motion?` 把业务错误提升为本域失败 | `Execution` 的 `Err` |
| 合作式停止 | 外部调用 `request_stop()` | `Execution` 的 `Ok(Completion::Stopped)` |

`Execution<T>` 是 `Result<Completion<T>, RoplatError>`，`Completion<T>` 是 `Completed(T)` 或 `Stopped`。停止不是错误：它没有业务值，但也没有失败。

## 一段失败，父层决定怎么办

```rust
tasks >> |goal| {
    goal >> segment >> |goal| {
        &mut arm >> motion.resources.0;
        goal >> motion;
        motion?
    };
    goal >> report.input.0;
    segment.outcome >> report.input.1;
};
```

`segment` 是 `once()` 节律：每次 drive 只运行一个周期，用来把一组节点包成一个可以单独处理结果的子域。周期域以 `motion?` 结尾：成功时 Feed 是 `()`，失败时这个子域失败。

父层读取子节律结果有两种写法：

- `segment.output`（或直接写 `segment`）：读取正常完成时的 Output。子域失败或停止时，**默认向父域传播**，依赖它的后续节点不会运行。
- `segment.outcome`：把完整的 `Execution<Output>` 交给父图处理。这里交给 `report` 记录，任务器继续下一段。

同一个子节律只能选其中一种写法。`.outcome` 只隔离这个子域自己的失败；父域已经收到的停止请求，它不能撤销。

## 从外部停止

```rust
#[roplat::system(context = context)]
async fn monitor(context: ExecutionContext, sampler: &mut Sampler) -> Execution<()> { ... }
```

- `context = context` 让 System 使用调用方传入的停止上下文。调用方保留它的一个 clone，就能随时 `request_stop()`。
- 返回类型写成 `Execution<T>`，停止时得到 `Ok(Completion::Stopped)`。写成 `RoplatResult<T>` 也可以，但停止会被表示为 `Err(RoplatError::Stopped)`；返回普通值的 System 在失败或停止时会在收尾后 panic。
- 节律在每个周期开始前观察停止请求；正在运行的周期会完整结束，交回对象之后才退出。
- 停止是粘性的：一个上下文停止后不会恢复。要重新运行，创建新的上下文。`context.child()` 创建子上下文：父停止会传到子，子停止不影响父和兄弟。

## 收尾顺序

输出里 `log closed` 出现在 `monitor: stopped` 之前：System 先等在途的周期结束、取回对象，再按创建的逆序调用本层对象的 `on_shutdown`，最后才返回。整个过程是：

1. 请求停止，不再开始新的工作。
2. 已经开始的周期和分支完整返回，交回它们用到的对象。
3. 创建层关闭自己创建的对象。

参数传进来的 `sampler` 不由 System 关闭；调用方在 System 返回后还能读取它的计数。

## 保证的边界

合作式失败和停止保证等待在途工作并归还对象。以下情况不在保证内：panic、丢弃 System 的 Future、任务被 abort，以及节点里不合作的无限循环或阻塞调用。

`request_stop()` 是软件层面的请求，不会自动让设备进入安全状态，也不会撤回已经发出的指令。设备怎样保持、减速、确认停止，由驱动定义。

下一篇：[多设备与旁路](sideband.md)。
