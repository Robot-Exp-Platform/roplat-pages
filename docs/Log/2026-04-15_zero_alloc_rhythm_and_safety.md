# 2026-04-15 零分配节律驱动与编译期安全增强

## 概述

本次更新包含四项改进：

1. **消除 `BoxFuture` 逐 tick 堆分配** — Rhythm trait 改为 pass-by-value 泛型方案
2. **跨组死锁编译期检测** — 在图规约后自动检测通道依赖环路
3. **自动拓扑可视化** — `cargo roplat topology` 生成 Mermaid / DOT 图
4. **编译错误人性化** — System DSL 解析器增加 span 精确的中文错误提示

## 1. 零分配 Rhythm::drive

### 问题

原 `Rhythm::drive` 的回调签名为：

```rust
F: for<'a> FnMut(&'a mut N, Self::Yield) -> BoxFuture<'a, Self::Feed> + Send
```

每个 tick 都通过 `Box::pin(async move { ... })` 在堆上分配 future。对于 1kHz 控制循环，这意味着每秒 1000 次 `malloc + free`。

### 方案：Pass-by-Value

核心观察：`BoxFuture` 之所以必要，是因为回调的返回类型依赖于 `&'a mut N` 的生命周期参数，无法用单一泛型 `Fut` 表达。

解决方法：将 `N` 从引用传递改为值传递，节点元组在每个 tick 移入移出：

```rust
fn drive<N, F, Fut>(&mut self, nodes: N, op_domain: F)
    -> impl Future<Output = Self::Output> + Send
where
    N: Send,
    F: FnMut(N, Self::Yield) -> Fut + Send,
    Fut: Future<Output = (Self::Feed, N)> + Send;
```

回调返回 `(Feed, N)` 元组，将 `N` 的所有权还给 `drive` 循环。由于 `N` 实际是可变引用的元组（即指针），移动成本为零。

### 失败路径

| 尝试 | 方案 | 结果 |
|------|------|------|
| #1 | `async FnMut(&mut N, Y) -> F + Send` | `async_trait_bounds` 不稳定 |
| #2 | 加 `#![feature(async_trait_bounds)]` | `CallRefFuture<'_>` 不满足 `Send` |
| #3 | Pass-by-value `FnMut(N, Y) -> Fut` | ✅ 编译通过，所有测试通过 |

### 影响范围

- `roplat/src/rhythm.rs` — trait 定义
- `roplat/src/rhythm/{sys_timer,count_rhythm,iterator,event_trigger}.rs` — 所有 impl
- `roplat_macros/src/system/codegen.rs` — 代码生成
- `roplat/tests/{count_rhythm_test,iterator_rhythm_test}.rs` — 17 个测试

## 2. 跨组死锁编译期检测

### 机制

图规约（R0-R4）后，独立执行单元通过通道通信。新增 `ReduceOutput::detect_channel_deadlock()` 方法：

1. 提取独立执行单元（`Spawned` / `Par` 子树 + offloaded 任务）
2. 收集每个单元的 `ChannelTx` / `ChannelRx` ID
3. 构建单元间依赖图：单元 A 有 `Rx(ch)` 且单元 B 有 `Tx(ch)` → A 依赖 B
4. DFS 检测环路

若检测到环路，在 `schedule_graph_v3()` 中 panic，阻止编译。

### 测试覆盖

- 单执行单元（无死锁）
- 独立单元无通道（无死锁）
- 单向通道（无死锁）
- 双向环路（检测到死锁）
- 三单元环路（检测到死锁）
- 主图与 offloaded 间死锁
- 流水线通过 offloaded（无死锁）

共 7 个新增测试。

## 3. cargo roplat topology

新增 `Topology` 子命令：

```bash
cargo roplat topology arch.yaml                    # stdout Mermaid
cargo roplat topology arch.yaml --format dot       # stdout DOT
cargo roplat topology arch.yaml -o graph.mmd       # 写入文件
```

- **Mermaid**：节律域分组为 `subgraph`，资源用圆角矩形虚线连接
- **DOT**：节律域分组为 `cluster_*`，资源用椭圆虚线节点

## 4. System DSL 错误人性化

`SystemParser` 新增 `errors: Vec<syn::Error>` 字段，替换原有的静默 `_ => {}` 分支：

| 场景 | 原行为 | 新行为 |
|------|--------|--------|
| 不支持的语句类型 | 静默忽略 | 报错："暂不支持宏调用语句" |
| 无法识别的表达式 | 静默忽略 | 报错 + 列出支持的语法 |
| 无法解析的端点 | 静默忽略 | 报错："期望格式 `node` 或 `node.port`" |
| 节律域驱动源解析失败 | 静默忽略 | 报错："期望格式 `timer >> \|event\| { ... }`" |

所有三个解析入口（`expand_system_from_file`、`expand_system`、`expand_system_inline`）已接入错误检查。
