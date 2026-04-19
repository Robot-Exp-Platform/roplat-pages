# 2026-04-17 System 宏分号/表达式 Feed 语义

## 背景

System DSL 中节律域块的 Feed 类型需要由宏自动推导。之前无论块末尾是否有分号，Feed 都被默认为 `()`，导致需要 Feed 反馈的场景无法使用。

## 变更

### 核心思路

利用 Rust 的语句/表达式区分：块中最后一条链**无分号**时，其输出作为 Feed；**有分号**时，Feed 为 `()`。这与 Rust 函数体返回值的语义完全一致。

### 修改文件

- `roplat_system/src/system_v3/ir.rs`：`Subgraph::Rhythm` 新增 `trailing_expr: bool` 字段
- `roplat_system/src/system_v3/parser.rs`：解析块时检测末尾是否为表达式（含内联闭包 `|state| state >> node` 的特殊处理）
- `roplat_system/src/system_v3/codegen.rs`：根据 `trailing_expr` 决定是否将最后一条链的输出作为 Feed 返回

### 测试

新增 46 项测试，覆盖：

- 基础分号/无分号
- 多条链混合（部分有分号、最后一条无分号）
- 闭包形式 `|state| { ... }`
- 内联闭包 `|state| state >> node`
- 嵌套 match/if 中的 trailing expression

全部通过。
