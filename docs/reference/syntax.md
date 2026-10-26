# 语法速查

roplat 0.5 System DSL 的写法汇总。片段里的节点名不是关键字；类型与函数签名以 [docs.rs](https://docs.rs/roplat/0.5.0/roplat/) 为准。

## 入口

| 写法 | 说明 |
|---|---|
| `#[roplat::system] async fn run(…) -> R` | 具名 System，调用方 `.await`；参数对象只被使用，不由本层启停 |
| `#[roplat::system] async fn main()` | 自动补 Tokio 入口 |
| `#[roplat::system]` 写在 `#[tokio::main(…)]` 外层 | 指定 Tokio 配置 |
| `#[roplat::system(context = ctx)]` | 使用调用方的停止上下文 |
| `#[roplat::system(file = "arch.yaml")]` | 从 YAML 读取拓扑，见 [YAML 文件入口](../integrate/yaml.md) |
| `roplat::system_item! { … }` | 在 async 代码里内联一段图；失败或停止时 panic |

返回类型推荐 `Execution<T>`；`RoplatResult<T>` 把停止表示为 `Err(RoplatError::Stopped)`；普通返回值在失败或停止时 panic。

## 结构

每个 System、周期域、match 分支：**普通 Rust 头段 → 连续的图 → 普通 Rust 尾段**。

- 图中段不能插入普通 Rust 语句；`loop` / `for` / `while` 不会被当作图。
- 周期和 match 分支的头段里不能用会跳出本层的 `?` 或 `return`。
- 尾段里的名字是对象本身；引用节点输出写 `node.output`。返回值写成 `Ok(…)` 等完整表达式。

## 连线与端口

| 写法 | 含义 |
|---|---|
| `a >> b >> c;` | 依赖链 |
| `node;` | 独立调用，没有输入时 Input 为 `()` |
| `a >> b; a >> c;` | a 调用一次，结果扇出 |
| `a.field >> b`、`a.0 >> b` | 取输出字段或元组成员（图语句里省略 `.output`） |
| `a >> c.input.0; b >> c.input.1;` | 按编号装配元组输入，编号从 0 连续 |
| `a >> b.input` | 整体输入（与 `a >> b` 相同） |
| `&value >> b` | 头段值或函数参数的一份副本，需要 `Clone` |
| `a >> b.trigger` | 只建立依赖，不传数据 |
| `a?`、`a.1?;` | 把业务 `Result` 提升为本域失败 |
| `&mut dev >> b.resources.N` | 把设备借给 b 的一次调用 |
| `roplat::node::map(|x: f64| x * 2.0)` | 中段的小计算 |

不支持：字面量 `3 >> sink`、调用 `f() >> sink`、下标 `a.output[0] >> sink`、算术 `(a + b) >> sink`、目标端命名字段 `b.input.position`、一个目标同时用整体与编号输入、多个来源连到裸目标。

## 节律域

| 写法 | 含义 |
|---|---|
| `r >> { node; };` | 不绑定 Yield；周期 Feed 为 `()` |
| `r >> |y| { y >> node; };` | 绑定每周期 Yield |
| `r >> |(a, b)| { … };` | 解构 Yield |
| `src >> r >> |y| { … };` | src 的输出作为 Input |
| `src >> r.input;` 再单独定义域 | Input 与域分开写 |
| `r >> |y| { …; last }` | `last` 没有分号：它的输出是本周期 Feed |
| `r >> move |y| { … };` | 拥有型域，节点与资源以本体进入；hard 节律只能这样进入 |
| `async |y| -> RoplatResult<F> { … }` | 显式可失败的周期 |
| `r.output`、`r` | 整次 drive 的 Output；失败或停止默认向父域传播 |
| `r.outcome` | 完整的 `Execution<Output>`，由父图处理；与 `.output` 二选一 |

`|a, b|` 多参数、闭包属性和 `for`/`const`/`static` 限定会被拒绝。

## 分支

| 写法 | 说明 |
|---|---|
| `match node.output { P => { … } … }` | 只执行选中分支；直接端点建立依赖 |
| `P if cond => { … }` | 守卫是普通 Rust，只读模式绑定和普通值 |
| `if node.output { … } else { … }` | 图内 `if`，支持 `else if`、`if let` |
| `let x = match … { … };`、`let x = if … { … } else { … };` | 汇合各分支的尾值 |

结果绑定暂不支持 `let mut`、类型标注、解构和 let-else；条件不能写成 let 链。同一 match 的不同分支可以共用实例和资源。

## 资源

| 写法 | 说明 |
|---|---|
| `type Resources = ()` / `(A,)` / `(A, B)` | `process` 收到 `()` / `(&mut A,)` / `(&mut A, &mut B)` |
| `&mut a >> n.resources.0; &mut b >> n.resources.1;` | 每个资源一个槽，最多 16 个 |
| `x >> n2.trigger;` | 同一资源的两个使用者之间必须有依赖 |
| `child.outcome >> next.trigger;` | 用 `.outcome` 处理时建立依赖而不消费结果 |

资源绑定写在调用所在的作用域。不能写 `&mut a >> n`（不带槽号）、`n >> &mut a`、`&mut a.field`。

## 一个实例一个调用位置

同一名字在一张图里只代表一次调用。跨作用域也只能在一处调用（同一 match 的互斥分支除外）：在外层和内层各调用一次、尾段读取内层节点的 `.output`、两个都会运行的域共用实例，都会在编译时报错。

## 属性

绑定上的 `#[hard]` 已删除，改用 `rhythm.hard()`。`record`、`parallel`、`stop_check` 等 System 属性不受支持。图语句上的 `#[cfg]` 等属性会被拒绝；需要条件编译时，对整个函数或模块加 `#[cfg]`。
