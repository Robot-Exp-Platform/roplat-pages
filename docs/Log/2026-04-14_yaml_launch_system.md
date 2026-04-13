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

```rust
#[roplat::system(file = "arch.yaml")]
async fn main() {
    // __params 和 __registry 由生成代码使用
    let __params = roplat::roplat_launch::ParamConfig::from_yaml(
        &std::fs::read_to_string("params.yaml").unwrap()
    ).unwrap();
    let __registry = roplat::roplat_launch::ResourceRegistry::new();
    // YAML 生成的 DSL 会追加到此处
}
```

宏在编译期读取 `arch.yaml`（相对于 `CARGO_MANIFEST_DIR`），调用 `arch_to_tokens()` 生成 DSL 语句，与用户函数体合并后走完整管线。

### 方式二：`cargo roplat` CLI

```bash
# 验证架构文件
cargo roplat validate arch.yaml --params params.yaml

# 生成系统代码
cargo roplat launch arch.yaml -o generated_system.rs

# 列出库中可用节点
cargo roplat list-nodes --manifest-path path/to/Cargo.toml
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
| `validate <arch.yaml>` | 解析验证架构/参数文件，输出摘要 |
| `launch <arch.yaml>` | 生成完整系统 Rust 代码 |
| `list-nodes` | 设置 ROPLAT_PHASE=EXTRACT → cargo check → 读取节点 manifest JSON |

`list-nodes` 利用 `#[node]` 宏在 EXTRACT 阶段写入的 manifest 文件（`node_*.json`）来枚举所有可用节点。

## 测试覆盖

| 模块 | 测试数 | 内容 |
|------|--------|------|
| `arch.rs` | 7 | 解析、验证、循环检测、初始化顺序、hard 标记 |
| `param.rs` | 2 | 解析、参数查询 |
| `registry.rs` | 5 | 插入、获取、类型安全、Arc 共享 |
| `codegen.rs` | 3 | 基础生成、节律生成、资源生成 |

## 关键设计决策

1. **两文件分离**：架构需要重编译（触发 codegen），参数只需重启（运行时加载）
2. **复用现有管线**：`arch_to_tokens()` 生成 DSL TokenStream，送入 parser → graph → schedule → codegen，不重复实现调度逻辑
3. **feature gate**：`codegen` feature 仅在 proc-macro 和 CLI 中启用，运行时库不引入 syn/quote
4. **资源检测**：parser 通过 `__registry` 字符串匹配识别资源声明，与现有 `res::` / `Latest` 检测并列
