# hard 节律

运动规划、模型推理或一次长时间的外语调用，可能占住所在线程几十毫秒。把它放进普通节点，同一运行时上的控制环就会漏掉周期。hard 节律让一次 drive 在它自己的线程和运行时上执行，重计算不再拖住别人。

## 完整程序

规划域为三个目标各求解一次，每次占住线程 40 ms；控制域以 2 ms 的节拍跟随最新计划，并记录两次周期之间的最长间隔。程序断言这个间隔小于求解时间的一半。

<!-- roplat-example: hard -->
```rust
use std::time::{Duration, Instant};

use roplat::comm::{Latest, Publisher, Subscriber};
use roplat::rhythm::{IntoHard, IntoRhythm, WithPeriod, once};
use roplat::{Lifecycle, Node, RoplatError, RoplatResult};

const SOLVE_TIME: Duration = Duration::from_millis(40);

/// 规划器的替身：求解是同步的，会占住所在线程。
struct Planner;

impl Lifecycle for Planner {
    type Error = RoplatError;
}

impl Node for Planner {
    type Resources = ();
    type Input = f64;
    type Output = f64;

    async fn process(&mut self, goal: f64, _: ()) -> f64 {
        std::thread::sleep(SOLVE_TIME);
        goal
    }
}

/// 把规划结果交给控制域。
struct Publish {
    plans: Publisher<f64>,
}

impl Lifecycle for Publish {
    type Error = RoplatError;
}

impl Node for Publish {
    type Resources = ();
    type Input = f64;
    type Output = ();

    async fn process(&mut self, plan: f64, _: ()) {
        self.plans.publish(plan);
    }
}

/// 控制环：跟随最新计划，同时记录两次周期之间的最长间隔。
struct Follow {
    plans: Subscriber<f64>,
    position: f64,
    last: Option<Instant>,
    longest_gap: Duration,
}

impl Lifecycle for Follow {
    type Error = RoplatError;
}

impl Node for Follow {
    type Resources = ();
    type Input = u64;
    type Output = ();

    async fn process(&mut self, _tick: u64, _: ()) {
        let now = Instant::now();
        if let Some(last) = self.last.replace(now) {
            self.longest_gap = self.longest_gap.max(now - last);
        }
        if let Some(plan) = self.plans.latest() {
            self.position = *plan;
        }
    }
}

#[roplat::system]
async fn plan_while_controlling(goals: Vec<f64>) -> RoplatResult<(f64, Duration)> {
    let plans = Latest::<f64>::new(1);

    // 规划域：每个目标求解一次，求解在 plan 自己的线程上进行。
    let mut tasks = goals.into_iter().into_rhythm();
    let mut plan = once::<f64, f64>().hard();
    let mut planner = Planner;
    let mut publish = Publish {
        plans: plans.publisher(),
    };

    // 控制域：2 ms 一个周期，不受求解影响。
    let mut ticks = (0..150).with_period(Duration::from_millis(2));
    let mut follow = Follow {
        plans: plans.subscriber(0),
        position: 0.0,
        last: None,
        longest_gap: Duration::ZERO,
    };

    tasks
        >> |goal| {
            goal >> plan
                >> move |goal| {
                    goal >> planner;
                    planner
                };
            plan.output >> publish;
        };

    ticks
        >> |tick| {
            tick >> follow;
        };

    Ok((follow.position, follow.longest_gap))
}

#[tokio::main(flavor = "current_thread")]
async fn main() -> RoplatResult<()> {
    let (position, longest_gap) = plan_while_controlling(vec![0.2, 0.6, 0.4]).await?;
    // 去掉 .hard() 后，最长间隔约等于一次求解时间（40 ms）。
    assert!(
        longest_gap < SOLVE_TIME / 2,
        "control loop stalled: {longest_gap:?}"
    );
    println!("final plan followed: {position:.1}");
    println!("control loop kept its pace during planning");
    Ok(())
}
```
<!-- /roplat-example -->

输出：

<!-- roplat-output: hard -->
```text
final plan followed: 0.4
control loop kept its pace during planning
```
<!-- /roplat-output -->

去掉 `.hard()`（并把 `move |goal|` 改回 `|goal|`）再运行，断言失败：控制环的最长间隔约等于一次求解时间。

## 写法

```rust
let mut plan = once::<f64, f64>().hard();

tasks >> |goal| {
    goal >> plan >> move |goal| {
        goal >> planner;
        planner
    };
    plan.output >> publish;
};
```

- `rhythm.hard()`（来自 `roplat::rhythm::IntoHard`）把任意节律变成 hard 节律。这里用 `once()`：每个目标一次 drive，一个周期。
- hard 节律只能由**拥有型域** `move |…| { … }` 进入。域里用到的节点以本体移到 hard 线程，drive 结束后随结果交回；节律借用的资源也以本体移入、交回。被移动的对象必须是 `Send + 'static`，并且由创建层以本体持有。
- 写成 `|goal| { … }` 时，编译错误会指向这个域并提示改用 `move`。
- 下游照常等待 hard 域的结果：`plan.output >> publish` 要等这次求解结束。

## 规划与控制是兄弟域

规划域和控制域之间没有图边，只经 `Latest` 交接。控制域每个周期读最新计划，还没有新计划时继续执行旧的。可能超过控制周期、而控制只需要最新结果的计算，都应这样放进自己的节律，经旁路交付，而不是放进控制周期里等待。

## 生命周期与异常

- 线程在第一次 drive 时启动，由创建层调用的 `on_shutdown` 关闭并等待。合作式退出、停止与失败的语义与普通节律相同，对象都随 drive 交回。
- 调用方的 Future 被丢弃（例如被 `timeout` 或 `select!` 取消）时，hard 线程不会被强行终止：这次 drive 被放弃并收到停止请求，它的结果和对象在 hard 线程上丢弃；下一次 drive 只返回自己的结果。
- hard 线程里发生 panic 后，移入的对象随之丢失，这个 hard 节律不能再用，之后的每次 drive 立即返回框架错误。
- 每次进入 hard 节律有几微秒的线程交接开销，适合重计算，不适合轻量节点。

## 不用 spawn 隔离重计算

System 只在根作用域把互不依赖的部分放进独立的 Tokio 任务；节律周期和 match 分支里的并发一律在同一任务内完成。即使放进独立任务，同步阻塞的代码一样会占住它所在的线程。所以隔离重计算的办法是 hard 节律，而不是寻找 spawn 的写法。详见[并发与放置](../concepts/placement.md)。

0.5 的 hard 节律还没有实时优先级和绑核参数；它隔离的是线程，不提供硬实时保证。

## 教程到此结束

接下来可以：

- 读[概念](../concepts/node.md)，了解每个设计背后的理由；
- 用[语法速查](../reference/syntax.md)和[常见编译诊断](../reference/diagnostics.md)查写法；
- 把 C++ 或 Python 算法接进来：[C++ 与 Python 节点](../integrate/languages.md)。
