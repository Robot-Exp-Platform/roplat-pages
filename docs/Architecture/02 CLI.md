# CLI 工具

`cargo-roplat` 提供 `cargo roplat ...` 子命令，用于生成、验证、可视化和诊断。

## 常用命令

```powershell
cargo roplat validate arch.yaml
cargo roplat generate arch.yaml --out-dir roplat
cargo roplat codegen arch.yaml --output roplat/arch.rs
cargo roplat run arch.yaml params.yaml
cargo roplat topology arch.yaml --format mermaid
cargo roplat expand src/main.rs --output expanded.rs
cargo roplat ipc ls
```

## YAML launch

arch YAML 大致形状：

```yaml
version: "0.1"
default_crate: my_robot

rhythms:
  - id: timer
    type: roplat::rhythm::CountRhythm

nodes:
  - id: source
    class: Source
    rhythm: timer
  - id: sink
    class: Sink
    rhythm: timer

topology:
  - from: source
    to: sink
```

使用 `validate` 先检查：

```powershell
cargo roplat validate arch.yaml
```

## 生成入口文件

```powershell
cargo roplat generate arch.yaml --out-dir roplat
```

如果 CLI 提示添加 bin target，在 `Cargo.toml` 中加入：

```toml
[[bin]]
name = "arch"
path = "roplat/arch.rs"
```

## 拓扑图

```powershell
cargo roplat topology arch.yaml --format mermaid
cargo roplat topology arch.yaml --format dot --output topology.dot
```

适合 code review、论文图、调试 launch 配置。

## 展开 system 宏

```powershell
cargo roplat expand src/main.rs --output expanded.rs
```

当你不理解 `#[roplat::system]` 生成了什么时，用 expand 看展开结果。

## IPC 诊断

```powershell
cargo roplat ipc ls
cargo roplat ipc ls --json
cargo roplat ipc introspect "roplat-ipc://<namespace>/<name>?msg=<schema>&v=<version>"
```

用于查看 rendezvous 目录中的活跃端点、schema、版本、pid 和地址。

## 什么时候用 CLI

| 需求 | 命令 |
|---|---|
| 检查 launch YAML | `validate` |
| 从 YAML 生成 Rust entry | `generate` / `codegen` |
| 看系统拓扑 | `topology` |
| 看宏展开 | `expand` |
| 查 IPC 端点 | `ipc ls` / `ipc introspect` |

普通 Rust-only 项目不一定需要 CLI；直接写 `#[roplat::system]` 往往更简单。
