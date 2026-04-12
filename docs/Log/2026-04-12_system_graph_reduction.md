# 2026-04-12 System 图规约引擎 (system_v3)

## 工作概述

重新设计并实现 `#[roplat::system]` 宏的核心调度算法：**可规约图 (ReducibleGraph)**。

核心思想：**图即调度，规约即编译**。用一种自包含的数据结构 `ReducibleGraph` + `RNode`
同时充当依赖图和调度树。反复应用 4 条规约规则，直到图收缩为单一节点——该节点即为最终的
执行调度计划。

## 设计动机

v2 实现存在 4 层数据结构映射 (IR → FlowGraph → Ranker 内部图 → Schedule)，
调试和测试困难。新方案将这些统一为一个结构，任何中间状态都可以直接序列化 / 打印观测。

## 数据结构

```rust
enum RNode {
    Atom(NodeId),           // 原子计算节点
    ChannelTx(ChannelId),   // 通道发送端
    ChannelRx(ChannelId),   // 通道接收端
    Seq(Vec<RNode>),        // 顺序执行
    Par(Vec<RNode>),        // 并行执行 (tokio::join!)
    Spawned(Vec<RNode>),    // 独立任务 (tokio::spawn)
}
```

- `ReducibleGraph` 维护 `BTreeMap<NodeId, RNode>` + 前向/反向邻接表 + 权重表。
- 规约操作直接修改图：合并节点、移除边、更新邻接。
- 嵌套 Seq/Par/Spawned 在构造时自动展平。

## 规约规则

| 优先级 | 名称 | 条件 | 动作 |
|--------|------|------|------|
| R1 | 串行融合 | `out(u)==1 ∧ in(v)==1` | 合并为 `Seq(u, v)` |
| R2 | 并行融合 | 相同 `(in_set, out_set)` 且至少一侧非空 | 合并为 `Par(...)` |
| R3 | 拓扑序列 | 图的拓扑排序唯一（每层仅 1 个零入度节点）| 全部合并为 `Seq` |
| R4 | 通道切割 | R1-R3 均无法推进 | 启发式选边，将 Tx/Rx 嵌入端节点 |

### R3 的价值

R3 解决了"准线性图"（如三角形 A→B, A→C, B→C）R1 无法直接融合的问题。
此类图拓扑排序唯一 `[A, B, C]`，R3 直接产出 `Seq(A, B, C)`，无需 R4 引入通道。

### R4 通道切割设计

与 v2 不同，R4 **不新建图节点**——将 `ChannelTx` 追加到源节点的 `RNode`、
`ChannelRx` 前置到目标节点的 `RNode`，然后移除图边。这保持了图节点数不增长，
同时自然为后续 R1/R2 创造条件。

评分公式：`Score(u→v) = 100·Δlayer + 10·InDeg(v) − Weight(v)`

## 规约流程

```
loop {
    穷尽 R1 + R2;
    if 节点 ≤ 1 → break;
    if R3 成功 → continue;
    if 有边 && R4 成功 → continue;
    break;  // 剩余无边节点 → Spawned
}
```

## 测试覆盖 (22 个用例)

| 类别 | 测试 | 验证内容 |
|------|------|----------|
| 基础 | `empty_graph`, `single_node`, `two_connected`, `two_independent` | 边界条件 |
| 线性链 | `linear_chain_3`, `linear_chain_5` | R1 反复融合 |
| 经典形状 | `diamond`, `fork`, `gather`, `wide_parallel` | R2 + R1 组合 |
| R3 | `triangle_uses_r3`, `extended_triangle` | 唯一拓扑排序检测 |
| R4 | `asymmetric_needs_r4` | 通道切割 + 后续规约 |
| 独立分量 | `two_independent_chains`, `mixed_connected_and_independent` | Spawned 生成 |
| 复杂图 | `w_shape`, `pipeline_with_fork_and_gather` | 多规则协作 |
| 追踪 | `step_by_step_diamond` | 逐步验证中间状态 |
| 错误 | `self_loop_panics`, `cycle_panics` | 非法输入检测 |
| 辅助 | `display_does_not_panic`, `atom_ids_collects_all` | 工具方法 |

## 已知问题与后续

1. **Spawned 子节点顺序**：由 BTreeMap 的 key 序决定，合并产生的高 ID 节点排在后面。
   不影响语义正确性，但可能影响可读性。
2. **R4 启发式非最优**：当前评分公式倾向切长边/高入度边，但某些图形下可能不是最优切割
   （例如可能丧失并发机会的切割）。可未来引入回溯搜索或更精细的评分。
3. **嵌套子图**：当前实现为扁平图。`match` / `if` / `rhythm` 等嵌套子图将作为
   `RNode::Nested` 变体在后续 PR 中添加，内部递归使用同一套规约算法。
4. **Parser / Codegen**：本次只实现纯算法层，不依赖 `syn` / `quote`。
   DSL 解析器和代码生成器将在后续独立实现。

## 文件清单

| 文件 | 说明 |
|------|------|
| `roplat_macros/src/system_v3/mod.rs` | 模块入口 |
| `roplat_macros/src/system_v3/graph.rs` | ReducibleGraph + RNode + 4 条规约规则 + 22 个测试 |
| `roplat_macros/src/lib.rs` | 添加 `mod system_v3` |
