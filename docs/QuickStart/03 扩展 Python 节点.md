# 扩展 Python 节点

Python 支持位于 `roplat_py`，这样纯 Rust 或 C++ 下游不会被 PyO3 拖慢编译。

## 1. 增加依赖

`Cargo.toml`：

```toml
[dependencies]
roplat = { path = "../roplat/roplat" }
roplat_py = { path = "../roplat/roplat_py" }

[build-dependencies]
roplat_build = { path = "../roplat/roplat_build" }
```

如果你手写 PyO3 代码，使用 `roplat_py::pyo3`，不要使用 `roplat::pyo3`。

## 2. 定义消息

`src/msg.rs`：

```rust
#[roplat::roplat_msg(version = 1)]
#[repr(C)]
#[derive(Copy, Clone, Debug)]
pub struct Packet {
    pub id: u64,
    pub value: f64,
}
```

## 3. 声明 Python puppet

`src/puppet.rs`：

```rust
use crate::msg::Packet;

#[roplat::node(
    lang = "py",
    input(input, Packet),
    output(output, Packet),
)]
pub struct PyForward {
    pub bias: f64,
}

impl PyForward {
    pub fn with_bias(bias: f64) -> Self {
        Self { bias, ..Default::default() }
    }
}
```

## 4. 配置 build.rs

```rust
fn main() {
    if std::env::var("ROPLAT_PHASE").as_deref() == Ok("EXTRACT") {
        return;
    }

    roplat_build::BuildOrchestrator::new()
        .build()
        .expect("roplat code generation failed");

    println!("cargo:rerun-if-changed=src/msg.rs");
    println!("cargo:rerun-if-changed=src/puppet.rs");
    println!("cargo:rerun-if-changed=py/");
    println!("cargo:rerun-if-changed=build.rs");
}
```

## 5. 生成并实现 Python 文件

```powershell
cargo check
```

生成结构：

```text
py/
  roplat_gen/        # generated, do not edit
  py_forward.py      # user-editable
```

在用户文件里实现 `process`。生成 glue 会在运行时把 `py/` 和 `py/roplat_gen/` 放入 Python import path。

## 6. 在系统里使用

```rust
#[roplat::system]
async fn main() {
    let mut source = Source::default();
    let mut py = puppet::PyForward::with_bias(0.5);
    let mut sink = Sink;
    let (_, mut timer) = roplat::rhythm::create_count_rhythm(1);

    timer >> {
        source >> py >> sink;
    };
}
```

## 常见问题

- Python 节点 crate 必须显式依赖 `roplat_py`。
- 不要编辑 `py/roplat_gen`。
- 用户 Python 文件只在缺失时生成。
- 如果 import 失败，先检查 `cargo check` 是否生成了 stub，再检查文件名和类名是否与 puppet 对应。
