# 2026-04-14 YAML 文件启动系统实现

## 概述

实现了基于 YAML 文件的声明式系统启动机制，将原本需要手写 Rust DSL 的系统描述拆分为两种文件：

- **架构文件** (Architecture YAML) — 编译期读取，触发代码生成
- **参数文件** (Parameters YAML) — 运行时加载，修改无需重新编译

核心思路：YAML → `ArchConfig` → `arch_to_tokens()` → DSL TokenStream → 现有管线 (parser → IR → graph → schedule → codegen)。

## 架构

### 新增 crate

| Crate | 角色 | 说明 |
|-------|------|------|
| `roplat_launch` | 共享库 | YAML 解析、验证、codegen；被宏和 CLI 共同依赖 |
| `cargo-roplat` | CLI 工具 | `cargo roplat` 子命令：validate / launch / list-nodes |

### roplat_launch 模块结构

```
roplat_launch/src/
├── lib.rs        # 模块根
├── error.rs      # LaunchError 枚举
├── arch.rs       # ArchConfig + 验证 + 拓扑排序
├── param.rs      # ParamConfig (运行时参数)
├── registry.rs   # ResourceRegistry (类型安全资源容器)
└── codegen.rs    # arch_to_tokens() + generate_full_system_fn() [feature = "codegen"]
```

### 数据流

```
               编译期                          运行时
 ┌─────────┐  from_yaml()  ┌────────────┐         ┌─────────────┐
 │arch.yaml├──────────────►│ ArchConfig  │         │ params.yaml │
 └─────────┘               └──────┬─────┘         └──────┬──────┘
                                  │                       │
                    arch_to_tokens│              from_yaml│
                                  ▼                       ▼
                          ┌──────────────┐        ┌─────────────┐
                          │ DSL Tokens   │        │ ParamConfig  │
                          └──────┬───────┘        └──────┬──────┘
                                 │                       │
                      parser → graph                     │
                      → schedule → codegen               │
                                 │                       │
                                 ▼                       ▼
                          ┌──────────────────────────────────┐
                          │      运行时：节点构造 + 事件循环     │
                          └──────────────────────────────────┘
```

## 架构文件 Schema

```yaml
# arch.yaml
version: "1"          # 可选
default_crate: my_lib  # 可选，短名自动加此前缀

resources:
  - id: shared_buf
    type: "res::RingBuffer<SensorData>"

rhythms:
  - id: fast_loop
    type: SysTimer

nodes:
  - id: sensor
    class: SensorNode
    rhythm: fast_loop
    refs:                     # 资源引用映射 field_name → resource_id
      buffer: shared_buf
  - id: filter
    class: FilterNode
    rhythm: fast_loop
    depends_on: [sensor]
    hard: true               # 权重标记，影响调度

topology:
  - from: sensor
    to: filter
  - from: sensor.output.data
    to: filter.input.raw      # 支持端口级连接
```

### 验证规则

- 节点 `rhythm` 引用的节律必须在 `rhythms` 中声明
- 节点 `refs` 引用的资源必须在 `resources` 中声明
- `depends_on` 引用的节点必须存在
- 依赖关系不能有环（Kahn 算法检测）

## 参数文件 Schema

```yaml
# params.yaml
resources:
  shared_buf:
    capacity: 64

rhythms:
  fast_loop:
    period_ms: 10

nodes:
  sensor:
    sample_rate: 1000
  filter:
    alpha: 0.5
```

参数文件修改后无需重新编译，仅需重启程序。

## 使用方式

### 方式一：`#[system(file = "arch.yaml")]`

编译期宏展开，节点定义在同 crate 内：

```rust
use file_launch::{SourceNode, DoubleNode, PrinterNode};
use roplat::Node;
use roplat::rhythm::Rhythm;

#[roplat::system(file = "arch.yaml")]
async fn main() {
    let __params = roplat::roplat_launch::ParamConfig::from_yaml(
        &std::fs::read_to_string("params.yaml").unwrap()
    ).unwrap();
    let __registry = roplat::roplat_launch::ResourceRegistry::new();
    // YAML 生成的 DSL 会追加到此处
}
```

### 方式二：`cargo roplat generate` + `cargo roplat run`

纯 YAML 驱动，自动生成 `.rs` 入口文件并编译运行：

```bash
# 生成 .rs 到 roplat/ 目录（mtime 检测，arch 未变则跳过）
cargo roplat generate arch.yaml

# 生成 + 编译 + 运行（params 是运行时参数，换文件不触发重编译）
cargo roplat run arch.yaml params.yaml

# 强制重新生成
cargo roplat generate arch.yaml --force
```

`arch.yaml` 中通过 `default_crate` 字段自动为短类名补全 crate 前缀：

```yaml
default_crate: file_launch

nodes:
  - id: source
    class: SourceNode          # → file_launch::SourceNode
  - id: ext
    class: other_lib::ExtNode  # 已有完整路径，保持原样
```

生成的 `roplat/<stem>.rs` 包含完整 `use` 块和 `#[roplat::system] fn main()`，
注册为 `[[bin]]` target 后可直接 `cargo run --bin <stem>`。

### 方式三：`cargo roplat codegen`（预览代码）

```bash
# 输出代码到 stdout（调试用）
cargo roplat codegen arch.yaml

# 输出到文件
cargo roplat codegen arch.yaml -o out.rs
```

### 其他命令

```bash
# 验证架构和参数文件
cargo roplat validate arch.yaml params.yaml

# 列出库中可用节点
cargo roplat list-nodes
```

### 方式三：节点侧 `__system_new_from_launch`

`#[node]` 宏自动为每个节点生成 `__system_new_from_launch` 方法：

```rust
pub async fn __system_new_from_launch(
    yaml_params: &roplat::serde_yaml::Value,
    registry: &roplat::roplat_launch::ResourceRegistry,
    refs: &[(&str, &str)],  // (field_name, resource_id)
) -> RoplatResult<Self>
```

- `#[param]` 字段 → 从 YAML 反序列化
- `#[resource]` 字段 → 通过 refs 映射从 registry 获取
- `#[state]` 字段 → 使用默认值

## ResourceRegistry

类型安全的资源容器，以 `(id, TypeId)` 为键存储 `Arc<dyn Any + Send + Sync>`：

```rust
let mut reg = ResourceRegistry::new();
reg.insert("buffer", RingBuffer::<SensorData>::new(64));

// 节点内部通过 refs 获取
let buf: Arc<RingBuffer<SensorData>> = reg.get("buffer").unwrap();
```

## cargo-roplat 子命令

| 命令 | 功能 |
|------|------|
| `generate <arch.yaml>` | 生成 `.rs` 入口到 `roplat/` 目录，mtime 变更检测 |
| `run <arch.yaml> [params.yaml]` | generate + `cargo run --bin <stem> -- [params]` |
| `codegen <arch.yaml>` | 预览生成代码（stdout / `-o` 文件） |
| `validate <arch.yaml> [params.yaml]` | 解析验证架构/参数文件 |
| `list-nodes` | EXTRACT 阶段读取节点 manifest |

### 变更检测

`generate` / `run` 通过 mtime 比较避免不必要的重编译：

- `arch.yaml` mtime > `.rs` mtime → 重新生成
- `arch.yaml` 未变 → 跳过生成 → cargo 发现二进制无需重编译
- `params.yaml` 是运行时参数 → 换文件不触发重编译

## 测试覆盖

| 模块 | 测试数 | 内容 |
|------|--------|------|
| `arch.rs` | 11 | 解析、验证、循环检测、初始化顺序、hard 标记、`resolve_type_path`、`collect_use_paths` |
| `param.rs` | 2 | 解析、参数查询 |
| `registry.rs` | 5 | 插入、获取、类型安全、Arc 共享 |
| `codegen.rs` | 4 | 基础生成、节律生成、端点解析、完整文件生成（use 块） |

## 关键设计决策

1. **两文件分离**：架构需要重编译（触发 codegen），参数只需重启（运行时加载）
2. **复用现有管线**：`arch_to_tokens()` 生成 DSL TokenStream，送入 parser → graph → schedule → codegen，不重复实现调度逻辑
3. **feature gate**：`codegen` feature 仅在 proc-macro 和 CLI 中启用，运行时库不引入 syn/quote
4. **资源检测**：parser 通过 `__registry` 字符串匹配识别资源声明，与现有 `res::` / `Latest` 检测并列
