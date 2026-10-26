# 安装与第一个程序

本页从零建立一个 Rust 项目，运行一个完整的 roplat 程序：一串传感器读数经过低通滤波后打印出来，最后读回滤波器保留的状态。它不需要机器人或其他外部依赖。

## 准备工具链

roplat 0.5 使用 Rust 2024 edition。本站所有例程都在 **nightly** 工具链上编译和运行；0.5 还没有确定最低支持的 Rust 版本（MSRV），stable 工具链未经验证。

```sh
rustup toolchain install nightly
```

在项目根目录放一个 `rust-toolchain.toml`，让 Cargo 自动选用 nightly：

```toml
[toolchain]
channel = "nightly"
```

## 创建项目

```sh
cargo new roplat-hello
cd roplat-hello
```

在 `Cargo.toml` 中加入依赖：

```toml
[dependencies]
roplat = "0.5.0"
tokio = { version = "1", features = ["macros", "rt-multi-thread", "sync", "time"] }
```

`#[roplat::system]` 生成的代码直接使用 `tokio::` 路径，所以应用要自己依赖 Tokio。上面的特性组合覆盖本站全部教程。

!!! note "版本"
    0.4 及更早版本与 0.5 不兼容，crates.io 上更早的 0.2 系列也没有这些接口。请固定 `roplat = "0.5.0"` 并提交 `Cargo.lock`。从旧版本升级见[从 0.4 迁移](../reference/migration.md)。

## 完整程序

把 `src/main.rs` 换成下面的内容：

<!-- roplat-example: first-system -->
```rust
use roplat::rhythm::IntoRhythm;
use roplat::{Lifecycle, Node, RoplatError, RoplatResult};

/// 一阶低通滤波：每次收到一个读数，输出平滑后的值。
struct LowPass {
    alpha: f64,
    state: Option<f64>,
}

impl Lifecycle for LowPass {
    type Error = RoplatError;
}

impl Node for LowPass {
    type Resources = ();
    type Input = f64;
    type Output = f64;

    async fn process(&mut self, reading: f64, _: ()) -> f64 {
        let next = match self.state {
            Some(previous) => previous + self.alpha * (reading - previous),
            None => reading,
        };
        self.state = Some(next);
        next
    }
}

/// 把每个周期的结果打印出来。
struct Print;

impl Lifecycle for Print {
    type Error = RoplatError;
}

impl Node for Print {
    type Resources = ();
    type Input = f64;
    type Output = ();

    async fn process(&mut self, value: f64, _: ()) {
        println!("filtered = {value:.2}");
    }
}

#[roplat::system]
async fn smooth(readings: Vec<f64>) -> RoplatResult<f64> {
    // 头段：创建本层对象。
    let mut samples = readings.into_iter().into_rhythm();
    let mut filter = LowPass {
        alpha: 0.5,
        state: None,
    };
    let mut print = Print;

    // 图：每个读数是一个周期，依次经过滤波和打印。
    samples
        >> |reading| {
            reading >> filter >> print;
        };

    // 尾段：整次运行结束后读取对象状态。
    Ok(filter.state.unwrap_or_default())
}

#[tokio::main(flavor = "current_thread")]
async fn main() -> RoplatResult<()> {
    let last = smooth(vec![1.0, 3.0, 2.0, 4.0]).await?;
    println!("last = {last:.2}");
    Ok(())
}
```
<!-- /roplat-example -->

运行：

```sh
cargo run
```

输出：

<!-- roplat-output: first-system -->
```text
filtered = 1.00
filtered = 2.00
filtered = 2.00
filtered = 3.00
last = 3.00
```
<!-- /roplat-output -->

## 读懂这段程序

**节点只管一次计算。** `LowPass` 每次收到一个读数，返回平滑后的值；`Print` 把值打印出来。节点不知道自己被谁调用、多久调用一次。每个节点都实现两个 trait：`Lifecycle`（启用与关闭，默认什么也不做）和 `Node`。`type Resources = ()` 表示它不借用设备，`process` 的第三个参数因此是 `()`。

**System 函数分三段。** 每个 `#[roplat::system]` 函数、每个节律周期和每个 match 分支都按同样的顺序组织：

1. **头段**：普通 Rust，创建对象、准备配置。
2. **图**：一段连续的连线语句，用 `>>` 表示依赖。
3. **尾段**：普通 Rust，整张图运行结束后读取结果、组织返回值。

图的中间不能插入普通 Rust 语句；准备工作放头段，结果处理放尾段。

**节律产生重复。** `readings.into_iter().into_rhythm()` 把迭代器变成节律：每一项是一个周期。`samples >> |reading| { ... }` 定义这个节律的周期域，`reading` 是本周期节律交给图的值（称为 Yield）。程序里没有 `for` 循环：重复由节律负责，结构由图负责。

**创建位置决定对象活多久。** `filter` 在 System 头段创建，所以四个周期用的是同一个对象，`state` 一直保留，尾段还能读到最后的值。如果把它移到周期域里创建，每个周期都会得到一个新的滤波器，平滑就失效了。

**分号决定周期交回什么。** 周期域最后一条语句 `reading >> filter >> print;` 带分号，表示本周期交回节律的值（称为 Feed）是 `()`，这正是迭代器节律要求的类型。下一篇教程会写一个需要非空 Feed 的节律。

**尾段写成 `Ok(...)`。** 尾段里的名字是对象本身，所以 `filter.state` 读的是字段。返回值要写成 `Ok(...)` 这样完整的 Rust 表达式；只写一个裸名字或裸字段作为最后一行，可能被当成图里的节点。

System 函数仍是普通的 `async fn`，由调用方 `.await`。这里用 Tokio 的 `main` 启动运行时并打印结果；如果把 System 函数本身命名为 `main`，宏会自动补上 Tokio 入口。

## 下一步

- [学习路线](roadmap.md)：教程的顺序和每篇回答的问题。
- [节律的四个边界](../tutorial/rhythm-boundaries.md)：亲手写一个节律，分清每周期的值与整次运行的值。
