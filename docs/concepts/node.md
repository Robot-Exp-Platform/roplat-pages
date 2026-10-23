# Node

Node 是一次计算或一次设备操作：收到一个输入，产生一个输出。它不决定自己多久运行一次，也不知道输出交给谁。频率和循环属于 Rhythm，连接关系属于 System。

## 形状

```rust
use roplat::{Lifecycle, Node, RoplatError};

struct AddOne;

impl Lifecycle for AddOne {
    type Error = RoplatError;
}

impl Node for AddOne {
    type Resources = ();
    type Input = i64;
    type Output = i64;

    async fn process(&mut self, value: i64, _: ()) -> i64 {
        value + 1
    }
}
```

| 关联类型 | 含义 |
|---|---|
| `Resources` | 每次调用要借用的设备，见[资源借用](resources.md)。不借用时写 `()` |
| `Input` | 一次调用的输入；多个来源时是元组 |
| `Output` | 一次调用的输出，可以是任何类型，包括业务 `Result` |

`Node` 要求 `Lifecycle + Send + Sync`。`Lifecycle` 提供 `on_init` 和 `on_shutdown` 两个钩子，默认什么也不做，见[生命周期与执行结果](lifecycle.md)。

## 节点不拥有拓扑，也不拥有循环

不要在节点内部调用下游节点，也不要在节点里写 `loop` 反复处理输入：

```rust
// 不要这样写
async fn process(&mut self, (): (), _: ()) -> Output {
    loop {
        let state = read_state().await;
        self.controller.process(state, ()).await;
    }
}
```

拓扑写在 System 里，重复由 Rhythm 产生。这样图对读者和编译器都是可见的，生命周期、停止和对象归还也由框架统一处理。

## 消息就是 Rust 值

Input 和 Output 可以是标量、元组、结构体或枚举，不需要实现特定 trait，也不要求特殊内存布局（跨进程 IPC 的消息另有要求，见[通信](communication.md)）。

图边遵守 Rust 的所有权：`Copy` 值可以扇出给多个下游；非 `Copy` 的元组字段可以分别移动给不同下游；同一个 `String` 不会因为画了两条边就被自动复制。需要共享时，在数据类型里明确表达，例如输出 `Arc<T>`。

## 业务结果是数据

规划节点返回 `Result<Path, PlanError>`，表示"计算完成了，但没有找到路径"。这是一个普通的输出，下游可以据此重试、降级或报告原因，不会让整个程序失败。

只有在图里显式写 `planner?` 时，`Err` 才被提升为当前执行域的失败，错误类型需要能转换为 `RoplatError`。

## 小计算用闭包节点

图中段不能写算术表达式。一步很小的变换可以用 `roplat::node::map`：

```rust
let mut scale = roplat::node::map(|value: f64| value * 2.0);
sensor >> scale >> controller;
```

它是普通节点：不借用资源，生命周期钩子为空，闭包可以是 `FnMut` 并跨调用保留状态。需要资源、生命周期或在图外读取状态时，写一个具名节点类型。

## `#[roplat::node]` 不是必需的

手写的 Rust 节点只需实现 `Lifecycle` 和 `Node` 就能加入 System。`#[roplat::node]` 用于另外两件事：为 [YAML 文件入口](../integrate/yaml.md)生成启动工厂，以及声明 [C++ 与 Python 节点](../integrate/languages.md)。

## 内置节点

`roplat::node` 下有算术、逻辑比较、滤波（滑动平均、指数平均、中值、限速、死区、低通）和输出写入等基础节点，适合示例、测试和简单的数据处理。列表见[内置节点与节律](../reference/builtins.md)。
