# 查看静态图

System 写复杂之后，特别是检查 AI 写出的图时，把它画出来最直观。`cargo roplat graph` 在编译时由 System 宏写出图，与实际编译的结果一致。

## 安装与运行

```sh
cargo install cargo-roplat
cargo roplat graph -p my_app
```

需要 [Graphviz](https://graphviz.org/) 的 `dot` 命令输出 SVG、PNG 或 PDF；只要 DOT 文本时不需要。`dot` 不在 `PATH` 里时，用环境变量 `ROPLAT_GRAPHVIZ_DOT` 指定。

常用参数：

| 参数 | 作用 |
|---|---|
| `-p, --package <包>` | 只编译这些包，默认是工作区的默认成员 |
| `--system <函数>` | 只输出这个 System 函数 |
| `--view flow|schedule|both` | 视角，默认两者都输出 |
| `--format svg|png|pdf|dot` | 格式，默认 SVG |
| `-o, --output <目录>` | 输出目录，默认 `<target>/roplat-graph` |
| `--all-targets` | 同时编译测试、示例等全部目标 |

输出文件位于 `<target>/roplat-graph/<包>/<crate>/<函数>.<视角>.<格式>`。

## 两种视角

- **flow**：你写的图。节点端口、节律域、match 分支、`.resources.N` 资源借用都会画出来。
- **schedule**：规约后的调度树，用串行、并行和 spawn 节点表示执行结构，并标出切开图时使用的通道。

flow 用来核对连线是否符合意图；schedule 用来理解哪些部分会并发、哪里会切开。

## 说明

- 命令使用独立的 target 目录，以 `roplat` 的 `graph` 特性编译，不影响平常的构建。
- 应用也可以直接打开 `roplat = { version = "0.5.0", features = ["graph"] }`；库不要打开这个特性，因为特性会在依赖图中合并。
- 旁路通信和内联的 `system_item!` 不会画出；同一个 crate 里同名的 System 会互相覆盖输出文件。
