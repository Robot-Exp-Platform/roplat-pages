# 系统 System

System 是 roplat 的拓扑层。它回答“谁连接谁”，并把你写的 DSL 编译成可执行调度代码。

## 最小系统

```rust
#[roplat::system]
async fn main() {
    let mut source = Source::default();
    let mut add_one = AddOne;
    let mut sink = Sink;
    let (_, mut timer) = roplat::rhythm::create_count_rhythm(3);

    timer >> {
        source >> add_one >> sink;
    };
}
```

这里有两层 `>>`：

- `timer >> { ... }`：声明节律域。
- `source >> add_one >> sink`：声明数据流。

## 连接形式

线性链：

```rust
timer >> {
    source >> filter >> controller >> sink;
};
```

显式端口：

```rust
timer >> {
    imu.output.accel >> estimator.input.0;
    imu.output.gyro >> estimator.input.1;
    estimator.output.pose >> controller.input;
};
```

节律 yield：

```rust
timer >> |tick| {
    tick >> monitor.input;
};
```

分支：

```rust
timer >> {
    camera >> detector;

    match detector.output {
        Some(target) => {
            target >> tracker.input;
            tracker >> sink;
        }
        None => (),
    }
};
```

## 分号和 Feed

普通 pipeline 最后一行加分号：

```rust
timer >> {
    source >> sink;
};
```

这表示本轮 feed 是 `()`。

如果块尾是表达式，宏会把尾表达式作为 feed 推导：

```rust
rhythm >> |state| {
    state >> node;
    node.output
};
```

只有当 Rhythm 需要反馈值时才使用尾表达式。大多数下游项目保持分号即可。

## System 做了什么

`#[roplat::system]` 会在编译期：

1. 解析 system body 中的 DSL。
2. 构建 flow graph。
3. 推导依赖和调度。
4. 插入必要的生命周期调用。
5. 展开为 async Rust 执行代码。

你不需要手动创建 runtime graph，也不需要在运行期注册节点。

## 文件形式

除了直接写函数，系统宏也支持文件入口：

```rust
#[roplat::system(file = "roplat/arch.yaml")]
async fn main() {}
```

实际项目里更常见的是直接写 `#[roplat::system]`，或通过 `cargo roplat generate/codegen` 从 launch YAML 生成入口文件。

## 常见错误

- 在 system 外使用 `>>` 期待 roplat 语义。
- 用 sideband buffer 替代普通节点边。
- 在 node 内部手动调用下游 node。
- 忘记为普通 pipeline 的最后一行加分号，导致 feed 类型意外改变。
- 在下游项目中假设有运行时插件注册中心。
