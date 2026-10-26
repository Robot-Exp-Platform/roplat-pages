# System 与图

`#[roplat::system]` 把一个 `async fn` 里的连线语句当作一张依赖图，在编译期转换成 Rust 异步代码：哪些部分可以并发、哪些必须等待、对象怎样在各部分之间借出和交回、失败和停止怎样传播。最终的类型与借用仍由 Rust 编译器检查。

## 三种入口

```rust
#[roplat::system]
async fn run(mut source: Source, mut sink: Sink) -> roplat::RoplatResult<()> {
    source >> sink;
    Ok(())
}
```

- **具名 System 函数**：最常用。它仍是普通的 async 函数，由调用方 `.await`。参数传进来的对象只被使用，不由这一层启用或关闭。
- **名为 `main` 的 System**：没有 `#[tokio::main]` 时宏会自动补上。需要指定 Tokio 配置时，把 `#[roplat::system]` 写在 `#[tokio::main(...)]` 外层。
- **`roplat::system_item! { … }`**：在已有的 async 代码里内联一段图。它没有返回类型可以表达失败或停止，遇到时会在收尾后 panic；需要清楚的结果边界时用具名函数。

`#[roplat::system(context = expr)]` 使用调用方提供的停止上下文；`#[roplat::system(file = "arch.yaml")]` 从 YAML 文件读取拓扑，见 [YAML 文件入口](../integrate/yaml.md)。

## 头段、图、尾段

每个 System、每个节律周期、每个 match 分支都按同样的顺序组织：

```text
普通 Rust 头段 → 一段连续的图 → 普通 Rust 尾段
```

头段创建对象、准备配置；尾段在图运行结束后读取结果、返回值。图的中间不能插入普通 Rust 语句，`loop`、`for`、`while` 也不会被当作图。重复由节律产生，分支用图内 `match` 和 `if`。

语句是图还是普通 Rust，按语法形状判断：顶层的 `>>` 表达式、`match`、`let x = match …`、单独的节点名和 `node?` 都属于图。返回值请写成 `Ok(value)` 这样完整的 Rust 表达式；只写裸名字或裸字段作为最后一行，可能被当成图里的节点。

## 边表示依赖

```rust
sense >> plan >> act;
sense >> log;
```

`sense` 只运行一次，结果交给 `plan` 和 `log`。图边声明的是依赖，不是执行顺序：`plan` 和 `log` 互不依赖，可能并发；书写顺序不影响调度。`a >> b >> a` 是环，编译报错。

**一个实例只有一个调用位置。** 同一个名字在一张图里出现多次，指的都是同一次调用。跨作用域也一样：一个实例不能在外层调用一次、又在内层域调用一次，也不能在两个都会运行的域里各调用一次；只有同一个 match 的不同分支可以共用。需要多次调用就创建多个实例，需要重复就用节律。

## 端口

| 写法 | 含义 |
|---|---|
| `a >> b` | a 的完整输出作为 b 的完整输入 |
| `a.position >> b`、`a.0 >> b` | 取输出的字段或元组成员 |
| `a >> c.input.0; b >> c.input.1;` | 装配元组输入，编号决定位置，与书写顺序无关 |
| `&gain >> c.input.2` | 头段值或函数参数的一份副本（需要 `Clone`） |
| `a >> b.trigger` | 只建立依赖，不传数据 |
| `a?` | 把 a 输出里的业务 `Result` 提升为本域失败 |
| `&mut arm >> b.resources.0` | 把设备借给 b 的一次调用，见[资源借用](resources.md) |

多个来源连到同一个目标时必须写 `.input.N`；一个目标不能同时用整体输入和编号输入。普通 Rust 值不会自动成为输入：`let n = 3; n >> sink;` 中的 `n` 会被当成节点，应写 `&n >> sink;`。

## 分支

```rust
let command = match planner.output {
    Ok(command) => command,
    Err(error) => {
        error >> fallback;
        fallback
    }
};
command >> actuator;
```

- 只执行选中的分支；被匹配表达式是节点输出、Yield 或模式绑定时，建立图依赖。
- `let name = match …` 或 `let name = if … { … } else { … }` 把各分支的尾值汇合成一个结果。
- 守卫 `pattern if cond` 是普通 Rust，只能读模式绑定和普通值，不能读节点输出。
- 图内 `if` 是对 `bool` 的 match，支持 `else if` 和 `if let`；条件写成 let 链会报错，请改写为 match。

完整示例见[分支、条件与重试](../tutorial/branches.md)。

## 结果类型

推荐可停止的 System 返回 `Execution<T>`：完成为 `Ok(Completion::Completed(value))`，停止为 `Ok(Completion::Stopped)`，失败为 `Err(error)`。返回 `RoplatResult<T>` 时，停止被表示为 `Err(RoplatError::Stopped)`。返回普通值的 System 在失败或停止时会在收尾后 panic，只适合入门程序。

## 宏负责什么

应用作者不需要手写：同任务并发的汇合、跨任务的所有权移交、对象在周期之间的借出和交回、失败时通知兄弟停止并等待它们交回对象、创建层的启用与关闭。这些由宏根据图静态规划。

宏不负责：节点内部的锁、外部协议的等待、任意用户代码的死锁，以及硬实时。完整写法见[语法速查](../reference/syntax.md)。
