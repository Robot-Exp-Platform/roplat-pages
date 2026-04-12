# 2026-04-13 系统宏增强与收尾清理

## 工作概述

本次工作围绕 `#[roplat::system]` 宏和节律系统进行四项增强，并完成文档对齐清理。

## 关键变更

### 1. CountRhythm 替代 OneShotTimer

chain_mixed 示例中自定义的 `OneShotTimer` 替换为官方 `CountRhythm`：

```rust
let (handle, timer) = roplat::rhythm::create_count_rhythm(1);
```

`CountHandle` 可在运行时调整触发次数，语义更清晰。

### 2. `#[roplat::system]` 支持标注 main

系统宏检测到 `fn main()` 时，自动内联 `tokio::runtime::Builder::new_multi_thread()` 构建运行时。用户不需要再叠加 `#[tokio::main]`，解决了 two-pass 构建中两个属性宏冲突的问题。

非 main 函数仍生成普通 `async fn`。

### 3. Rhythm::drive 移除 Sync 约束

将 `drive()` 的泛型约束从 `N: Send + Sync` 改为 `N: Send`，涵盖：

- `rhythm.rs` trait 定义
- `count_rhythm.rs`、`event_trigger.rs`、`sys_timer.rs`、`iterator.rs`（2 个 impl）

原因：节点元组以 `&mut` 引用传入 drive 闭包后逐一解包，不存在并发共享，`Sync` 从未被需要。

### 4. on_init / on_shutdown 自动注入

代码生成器（codegen.rs）在 `Subgraph::Rhythm` 分支中：

- drive 前：按声明顺序调用 `node.on_init().await`
- drive 后：按声明逆序调用 `node.on_shutdown().await`
- 节点以 `(&mut node, ...)` 引用传入 drive，确保 drive 结束后仍存活

chain_mixed 中 10 行手动 on_init 调用已移除。

### 5. system_item! 内联过程宏

新增函数式过程宏 `system_item!`，解析裸语句块（不包装函数签名）：

- `lib.rs` 入口使用 `syn::Block::parse_within` 解析
- `system.rs` 中 `expand_system_inline()` 执行完整管道
- `graph.rs` 连接端点无 Instance 时默认 `NodeKind::Compute`（非 Variable）

### 6. 文档清理

- `3 节律源.md`：Rhythm trait 签名更新为 `N: Send`
- `4 系统.md`：补充 main 检测、on_init/on_shutdown、system_item! 说明
- `8 图规约与系统宏.md`：补充代码生成阶段 &mut 传递与生命周期注入说明
- `TODO.md`：系统部分从"拓扑排序"更新为"v3 图规约引擎"，标记已完成项
- 删除 `debug_expanded.rs` 调试产物

## 验证

- `cargo run -p chain_mixed`：EXIT 0
- `cargo check -p macros`：通过
- `cargo test -p roplat_macros`：33/33 通过
