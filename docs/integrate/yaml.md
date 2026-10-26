# YAML 文件入口

简单的静态拓扑可以写在 YAML 文件里，由 `#[roplat::system(file = "arch.yaml")]` 在编译期读取，转换成与 Rust DSL 相同的 System。运行期参数放在另一个文件里，修改后只需重启程序。

!!! warning "能力小于 Rust DSL"
    YAML 入口没有周期闭包、Feed 尾表达式、嵌套节律或 match，也不能在不同节律组之间连线。需要这些结构时请直接写 Rust System。

## 架构文件

```yaml
# arch.yaml：编译期读取，修改后需要重新编译
default_crate: my_app

rhythms:
  - id: ticker
    type: roplat::rhythm::CountRhythm

nodes:
  - id: source
    class: SourceNode
    rhythm: ticker
  - id: double
    class: DoubleNode
    rhythm: ticker
  - id: printer
    class: PrinterNode
    rhythm: ticker

topology:
  - from: source
    to: double
  - from: double
    to: printer
```

```yaml
# params.yaml：运行时读取，修改后重启即可
rhythms:
  ticker:
    count: 5
nodes:
  source:
    start: 1
  double:
    factor: 2.0
```

## 节点与入口

文件入口要通过启动工厂创建节点，所以节点需要 `#[roplat::node]`，并用字段属性说明每个字段从哪里来：

```rust
#[roplat::node]
pub struct SourceNode {
    #[param]                    // 从 params.yaml 读取
    start: i64,
    #[state(default = "0")]     // 内部状态，按表达式初始化
    seq: i64,
}
```

`#[resource]` 标记的字段从资源注册表取得共享对象；这和 System 的 `.resources.N` 借用通道是两回事。

```rust
#[roplat::system(file = "arch.yaml")]
async fn main() {
    let __params: roplat_launch::ParamConfig = {
        let yaml = std::fs::read_to_string(
            std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("params.yaml"),
        )
        .expect("无法读取 params.yaml");
        roplat_launch::ParamConfig::from_yaml(&yaml).expect("params.yaml 解析失败")
    };
    let __registry = roplat_launch::ResourceRegistry::new();
    // arch.yaml 声明的节点、节律和拓扑由宏插入到这里
}
```

生成代码要求函数头段里有名为 `__params` 和 `__registry` 的对象，项目需要依赖 `roplat_launch = "0.5.0"`。文件路径相对于 crate 根目录。

## 字段

| 字段 | 作用 |
|---|---|
| `nodes[].id / class` | 实例名与节点类型 |
| `nodes[].rhythm` | 把节点放进一个节律组 |
| `nodes[].depends_on` | 构造与初始化的顺序，不会成为每周期的数据依赖 |
| `nodes[].refs` | 把字段名与资源 ID 交给启动工厂 |
| `rhythms[].id / type` | 声明节律，类型需要提供 `from_launch_params` |
| `resources[].id / type` | 从注册表取得资源 |
| `topology[].from / to` | 连线，支持数字元组端口，例如 `.output.0.1` → `.input.0.0` |

## 限制

- 只出现在 `nodes` 里、没有出现在任何连线中的节点不会被执行。
- 不同节律组之间的边、未分组节点与节律组节点之间的边都会被拒绝，不会自动建立旁路。
- `default_crate` 只被辅助的完整文件生成器使用；属性式入口里，短类型名仍需在函数可见范围内导入。
- YAML 解析成功不等于程序正确，类型和端口匹配仍由 Rust 检查。
- 修改 YAML 后要确认使用它的目标被重新编译；必要时在 `build.rs` 里加 `cargo:rerun-if-changed=arch.yaml`。

`cargo roplat` 提供 `validate`、`codegen`、`generate`、`run` 等子命令辅助检查和生成文件入口，用 `cargo roplat --help` 查看。
