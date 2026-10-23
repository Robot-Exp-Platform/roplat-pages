# 借用设备

机械臂、相机、夹爪这类设备需要排他访问：同一时刻只能有一个使用者向它发指令。roplat 不把设备当成在节点之间传递的消息，而是在每次调用时把它的可变借用交给使用者，调用结束借用就结束。

## 完整程序

先回零，再伺服 30 个周期。第一次从 0.3 出发，正常完成；第二次从 5.0 出发，超出回零范围，整次运行以错误结束。

<!-- roplat-example: resources -->
```rust
use roplat::rhythm::IntoRhythm;
use roplat::{Lifecycle, Node, RoplatError, RoplatResult};

const DT: f64 = 0.1;

/// 一个单轴模拟机械臂。真实项目里它是驱动库提供的设备句柄。
struct Arm {
    name: &'static str,
    position: f64,
    commands: usize,
}

impl Arm {
    fn new(name: &'static str, position: f64) -> Self {
        Self {
            name,
            position,
            commands: 0,
        }
    }

    fn command(&mut self, velocity: f64) {
        self.position += velocity * DT;
        self.commands += 1;
    }
}

impl Lifecycle for Arm {
    type Error = RoplatError;

    async fn on_init(&mut self) -> RoplatResult<()> {
        println!("connect {}", self.name);
        Ok(())
    }

    async fn on_shutdown(&mut self) -> RoplatResult<()> {
        println!("disconnect {}", self.name);
        Ok(())
    }
}

/// 设备拒绝执行的原因。
#[derive(Debug)]
enum Fault {
    OutOfRange(f64),
}

impl From<Fault> for RoplatError {
    fn from(fault: Fault) -> Self {
        match fault {
            Fault::OutOfRange(position) => {
                RoplatError::NodeProcessing(format!("起始位置 {position} 超出回零范围"))
            }
        }
    }
}

/// 回零：只在安全范围内执行。
struct Home {
    limit: f64,
}

impl Lifecycle for Home {
    type Error = RoplatError;
}

impl Node for Home {
    type Resources = (Arm,);
    type Input = ();
    type Output = Result<(), Fault>;

    async fn process<'call>(
        &'call mut self,
        (): (),
        (arm,): (&'call mut Arm,),
    ) -> Result<(), Fault> {
        if arm.position.abs() > self.limit {
            return Err(Fault::OutOfRange(arm.position));
        }
        arm.position = 0.0;
        Ok(())
    }
}

/// 每个周期向目标发一次速度指令，输出剩余误差。
struct Servo {
    gain: f64,
    limit: f64,
}

impl Lifecycle for Servo {
    type Error = RoplatError;
}

impl Node for Servo {
    type Resources = (Arm,);
    type Input = f64;
    type Output = f64;

    async fn process<'call>(&'call mut self, target: f64, (arm,): (&'call mut Arm,)) -> f64 {
        let error = target - arm.position;
        arm.command((self.gain * error).clamp(-self.limit, self.limit));
        target - arm.position
    }
}

/// 一次运行之后留给调用方的结果。
#[derive(Debug)]
struct Snapshot {
    position: f64,
    commands: usize,
}

#[roplat::system]
async fn home_then_move(start: f64, target: f64) -> RoplatResult<Snapshot> {
    // 机械臂由本层创建：本层负责连接与断开。
    let mut arm = Arm::new("left", start);
    let mut home = Home { limit: 2.0 };
    let mut ticks = (0..30).into_rhythm();
    let mut servo = Servo {
        gain: 3.0,
        limit: 1.0,
    };

    // 先回零：home 在 process 期间借用 arm；失败时整次运行以错误结束。
    &mut arm >> home.resources.0;
    home?;
    // 两个使用 arm 的地方必须有依赖：回零之后才开始伺服。
    home >> ticks.trigger;

    // 再伺服 30 个周期：每个周期 servo 借用一次 arm。
    ticks
        >> |_tick| {
            &mut arm >> servo.resources.0;
            &target >> servo;
        };

    // 尾段：arm 仍是本体，读取状态作为结果。
    Ok(Snapshot {
        position: arm.position,
        commands: arm.commands,
    })
}

#[tokio::main(flavor = "current_thread")]
async fn main() {
    match home_then_move(0.3, 1.0).await {
        Ok(snapshot) => println!(
            "reached {:.3} after {} commands",
            snapshot.position, snapshot.commands
        ),
        Err(error) => println!("failed: {error}"),
    }
    match home_then_move(5.0, 1.0).await {
        Ok(snapshot) => println!("unexpected: {snapshot:?}"),
        Err(error) => println!("failed: {error}"),
    }
}
```
<!-- /roplat-example -->

输出：

<!-- roplat-output: resources -->
```text
connect left
disconnect left
reached 1.000 after 30 commands
connect left
disconnect left
failed: 节点处理错误: 起始位置 5 超出回零范围
```
<!-- /roplat-output -->

## 声明要借用的设备

节点在 `type Resources` 里列出要借用的设备类型，`process` 的第三个参数就是这些设备的可变引用：

| `type Resources` | `process` 收到 |
|---|---|
| `()` | `()` |
| `(Arm,)` | `(&mut Arm,)` |
| `(Arm, Camera)` | `(&mut Arm, &mut Camera)` |

借用只在这一次 `process` 期间有效。节律也可以声明 `Resources`，那时借用覆盖整次 drive（见[多层节律](layers.md)）。

## 在图里借出

```rust
&mut arm >> home.resources.0;
home?;
home >> ticks.trigger;

ticks >> |_tick| {
    &mut arm >> servo.resources.0;
    &target >> servo;
};
```

- `&mut arm >> home.resources.0` 把 `arm` 借给 `home` 的第 0 个资源槽。借多个设备时依次连 `.resources.0`、`.resources.1`，编号从 0 连续。
- 设备不出现在 Input 或 Output 里。`home` 的输入是 `()`，输出是业务结果 `Result<(), Fault>`。
- 内层周期域里的 `servo` 也借用 `arm`。在外层看来，整个 `ticks` 域算作 `arm` 的一个使用者。

## 同一设备的使用者必须有先后

`home` 和 `ticks` 都使用 `arm`。roplat **只按图依赖**给它们排序，语句的书写顺序不算数。两者之间没有依赖时，宏会报错：

```text
error: resource `arm` is used by `home` and `ticks` with no data or `.trigger` dependency between them;
       uses of one resource are ordered only by graph dependencies, so add one, e.g. `home >> ticks.trigger;`
```

`home >> ticks.trigger` 只建立"在 home 之后"的依赖，不传递任何数据。如果两个使用者之间本来就有数据边，就不需要再补 `.trigger`。

## 业务错误与设备的去向

`home` 的输出是普通数据。`home?` 把其中的 `Err` 提升为本次运行的错误：图停止推进，`ticks` 不会开始，System 返回 `Err`。第二次调用的输出说明了两件事：

- 错误发生后，`arm` 仍然被正确断开（`disconnect left`）。借用在调用结束时就已结束，失败不会让设备"丢在"某个节点里。
- 不需要任何"归还"写法：没有返回边，也不需要把设备放进输出带回来。

!!! warning "0.5.0 的已知问题"
    在 0.5.0 中，把 `?` 和 trigger 边写在同一句里，例如 `home? >> ticks.trigger;`，**不会**传播错误，后续步骤照常运行。请像上面那样分成 `home?;` 和 `home >> ticks.trigger;` 两句。`?` 后面接数据边（`home? >> next;`）不受影响。

## 谁负责连接和断开

`arm` 在 System 头段创建，所以由这个 System 在开始时调用 `on_init`（连接）、结束时调用 `on_shutdown`（断开），出错和停止时也一样。如果 `arm` 是函数参数，System 只借用它，连接和断开由调用方负责。

尾段里 `arm` 仍是设备本体，可以直接读取字段。本层创建的设备要留到关闭钩子执行，所以尾段返回的是状态快照，而不是把 `arm` 本身移出去；参数传进来的设备则可以原样返回给调用方。

## 要点

- 设备是资源，不是消息：`&mut arm >> user.resources.N`，用完即还。
- 同一设备的任意两个使用者之间必须有数据边或 `.trigger` 边。
- 不同设备的使用者之间没有这个要求，可以并发。

下一篇：[分支、条件与重试](branches.md)。
