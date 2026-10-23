# 常见编译诊断

System 宏在展开时检查图的结构，诊断会标出相关的位置。下表按现象列出最常见的情况。

## 资源

| 现象 | 原因与改法 |
|---|---|
| `resource ... is used by ... and ... with no data or .trigger dependency between them` | 同一设备的两个使用者之间没有依赖。补一条数据边或 `a >> b.trigger;`；节律结果用 `.outcome` 处理时写 `child.outcome >> next.trigger;` |
| 旧写法 `&mut arm >> user`、`user >> &mut arm` 或归还边报错 | 0.5 改为独立借用通道：`&mut arm >> user.resources.0;`，设备不放进 Input/Output |
| `.resources.N` 的数量或类型不匹配 | 对照节点或节律的 `type Resources`，逐个连接，槽号从 0 连续 |
| 本层创建的设备缺少 `Lifecycle` | 借出本层创建的资源时，本层负责启停；为设备实现 `Lifecycle`，或改为参数传入 |
| 自定义节点报 `Sync` 约束 | `Node` 要求 `Send + Sync`，持有设备的节点需要设备类型满足它 |

## 调用位置与图结构

| 现象 | 原因与改法 |
|---|---|
| `... is called both in ... and in ...` | 同一实例在外层和内层（或两个都会运行的域）各调用了一次。读取域的结果，或创建两个实例；资源绑定移到调用所在的作用域 |
| `reading ... .output in this tail would call it a second time` | 尾段读取了内层节点的 `.output`。让该节点成为域的尾表达式，改读域的 `.output` |
| 图里有环 | `a >> b >> a` 不是"再调用一次 a"。跨周期的值放在节点状态里，或用 `feedback` 节律经 Feed 带到下一周期 |
| 多个来源连到同一目标被拒绝 | 写 `.input.0`、`.input.1`；语句顺序不决定元组位置 |
| 节点被当成普通 Rust，或普通 Rust 被当成节点 | 图被普通语句隔开，或放进了 `loop` / `for`。回到连续的图；中段计算用 `roplat::node::map`；裸数值写成 `&value >> x` |
| 守卫读取 `.output` 报错 | 守卫只读模式绑定和普通值；节点算出的条件用图内 `if` |
| 条件写成 let 链报错 | 改写为 match |

## 节律与放置

| 现象 | 原因与改法 |
|---|---|
| `a hard rhythm cannot be entered by a borrowing domain` | hard 节律的域写成 `move |…| { … }`；域内对象须 `Send + 'static`，由创建层以本体持有 |
| `#[hard]` 绑定属性报错 | 0.5 改为 hard 节律：`let mut step = once().hard();`，`goal >> step >> move |goal| { goal >> plan; plan };` |
| 加入独立分支或拥有型域后出现 `Send` / `'static` / 生命周期错误 | 跨任务或拥有型域需要对象本体；让创建层持有本体，不要用 unsafe 延长引用 |
| Feed 类型不匹配 | 检查周期尾表达式是否多了或少了分号；不要把子节律的 Output 和每周期 Feed 混淆 |

## 运行时现象

| 现象 | 首先检查 |
|---|---|
| 子节律后面的节点一直不运行 | 子节律这次 drive 是否真的会结束；Output 要等 drive 返回 |
| 事件或信号节律的域一直不结束 | 还有触发器存活；触发器不能交给同一 System 里的节点 |
| `fire_blocking` panic | 在 Tokio 运行时里调用了它；节点、周期和 hard 节律里用 `try_fire` 或 `fire_async().await` |
| 外部传入的节点没有初始化 | System 不启停参数对象，由创建层调用 `on_init` / `on_shutdown` |
| 每个周期状态都消失了 | 对象创建在周期内部；需要保留的状态放到外层 |
| 停止后再次运行立即返回 `Stopped` | 停止上下文是粘性的，新的运行用新的上下文 |
| 业务 `Result` 导致输入类型不对 | 业务结果默认是数据；需要提升时写 `node? >> next` 或单独的 `node?;` |
| 写了 `node? >> x.trigger;`，错误却没有传播 | 0.5.0 的已知问题，见[支持范围与已知问题](scope.md#已知问题) |

## 大图

约 150 个节点起 rustc 出现递归深度警告，约 200 个节点默认编译失败，需要在 crate 根加 `#![recursion_limit = "256"]`。
