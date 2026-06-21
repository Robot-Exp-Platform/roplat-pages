# 从零创建 Rust 项目

本页创建一个最小 Rust-only roplat 项目。

## 1. 创建 crate

```powershell
cargo new my_robot
cd my_robot
```

`Cargo.toml`：

```toml
[package]
name = "my_robot"
version = "0.1.0"
edition = "2024"

[dependencies]
roplat = { path = "../roplat/roplat" }
```

路径按你的 workspace 调整。

## 2. 定义节点

`src/nodes.rs`：

```rust
use roplat::{Node, RoplatError};

#[derive(Default)]
pub struct Source {
    seq: u64,
}

impl Node for Source {
    type Input = ();
    type Output = u64;
    type Error = RoplatError;

    async fn process(&mut self, _: Self::Input) -> Self::Output {
        self.seq += 1;
        self.seq
    }
}

pub struct AddOne;

impl Node for AddOne {
    type Input = u64;
    type Output = u64;
    type Error = RoplatError;

    async fn process(&mut self, input: Self::Input) -> Self::Output {
        input + 1
    }
}

pub struct Sink;

impl Node for Sink {
    type Input = u64;
    type Output = ();
    type Error = RoplatError;

    async fn process(&mut self, input: Self::Input) -> Self::Output {
        println!("value={input}");
    }
}
```

## 3. 写系统

`src/main.rs`：

```rust
mod nodes;

use nodes::{AddOne, Sink, Source};
use roplat::rhythm::create_count_rhythm;

#[roplat::system]
async fn main() {
    let mut source = Source::default();
    let mut add_one = AddOne;
    let mut sink = Sink;

    let (_, mut timer) = create_count_rhythm(3);

    timer >> {
        source >> add_one >> sink;
    };
}
```

这里 `timer` 负责执行 3 次，`source >> add_one >> sink` 负责数据流。

## 4. 运行

```powershell
cargo run
```

预期输出类似：

```text
value=2
value=3
value=4
```

## 5. 换成周期节律

如果要真实周期运行：

```rust
use std::time::Duration;

let mut timer = roplat::rhythm::SysTimer::new(Duration::from_millis(10));
```

然后保留同样的系统图：

```rust
timer >> {
    source >> add_one >> sink;
};
```

不要把周期逻辑写回 node 或手写 loop。

## 下一步

- 接 C++：读 [扩展 C++ 节点](02%20扩展%20C++%20节点.md)。
- 接 Python：读 [扩展 Python 节点](03%20扩展%20Python%20节点.md)。
- 理解 DSL：读 [系统 System](../Concepts/03%20System.md)。
