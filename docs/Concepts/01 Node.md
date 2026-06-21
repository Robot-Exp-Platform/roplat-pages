# 节点 Node

Node 是 roplat 中最小的计算单元。它接收一个输入，返回一个输出。

## 最小节点

```rust
use roplat::{Node, RoplatError};

struct AddOne;

impl Node for AddOne {
    type Input = i32;
    type Output = i32;
    type Error = RoplatError;

    async fn process(&mut self, input: Self::Input) -> Self::Output {
        input + 1
    }
}
```

这个节点没有线程、没有循环、没有通道。它只是一次计算。

## 生命周期

完整 trait 形状：

```rust
pub trait Node: Send + Sync {
    type Input;
    type Output;
    type Error: Into<roplat::RoplatError> + std::fmt::Debug + Send + Sync;

    async fn process(&mut self, input: Self::Input) -> Self::Output;

    async fn on_init(&mut self) -> Result<(), Self::Error> {
        Ok(())
    }

    async fn on_shutdown(&mut self) -> Result<(), Self::Error> {
        Ok(())
    }
}
```

使用建议：

- `process`：只放每一轮都要执行的热路径。
- `on_init`：打开设备、分配句柄、加载模型、启动连接。
- `on_shutdown`：关闭设备、flush、释放外部资源。

`process` 不返回 `Result`，这是有意设计。热路径保持简单，生命周期错误放在 init/shutdown。

## 节点不拥有拓扑

节点不应该知道自己连接谁：

```rust
// 不推荐：节点内部硬编码下游
impl Node for Sensor {
    async fn process(&mut self, input: ()) -> Output {
        let data = read_sensor();
        self.controller.process(data).await
    }
}
```

推荐：

```rust
timer >> {
    sensor >> controller;
};
```

这样系统图对宏和读者都是可见的。

## 节点不拥有循环

不要在普通节点里写：

```rust
loop {
    let input = read().await;
    self.process(input).await;
}
```

如果你需要“不断执行”，请选择或实现 Rhythm。

## 内置节点

`roplat::node` 下提供了一些基础节点：

| 模块 | 用途 |
|---|---|
| `node::arithmetic` | 加减乘除、绝对值、幂、平方根等 |
| `node::logic` | 逻辑、比较、位运算 |
| `node::filter` | 移动平均、指数平均、中值、限速、死区、低通 |
| `node::io` | stdout/stderr/debug/display writer |

这些适合示例、测试和简单数据处理。真实机器人项目通常会定义自己的节点。

## `#[roplat::node]`

普通 Rust 节点不一定需要 `#[roplat::node]`。当你需要 launch 参数、资源注入、manifest 信息或多语言 puppet 时才使用它。

Rust launch 辅助模式支持字段标记：

- `#[param]`：从 YAML 参数反序列化。
- `#[resource]`：从 launch registry 注入资源。
- `#[state]`：内部状态，默认初始化。
- `#[state(default = "...")]`：用表达式字符串初始化。
- `#[state(record)]`：参与旧 `Recordable` 记录。

多语言 puppet 模式见 [多语言编译管线](../Architecture/01%20Pipeline.md)。
