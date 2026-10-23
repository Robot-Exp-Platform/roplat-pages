# 生命周期与执行结果

一个对象要经过创建、启用、使用、关闭。roplat 的规则很简单：**谁创建，谁负责启用和关闭**。执行结果则分成三种：完成、合作式停止、失败。

## 创建层负责启用和关闭

```rust
pub trait Lifecycle {
    type Error: Into<RoplatError> + Debug + Send + Sync;
    fn on_init(&mut self) -> impl Future<Output = Result<(), Self::Error>> + Send { async { Ok(()) } }
    fn on_shutdown(&mut self) -> impl Future<Output = Result<(), Self::Error>> + Send { async { Ok(()) } }
}
```

| 对象在哪里创建 | 谁启用和关闭 | 活多久 |
|---|---|---|
| System 头段，且用于图 | 这个 System | 整次 System 运行，跨所有周期 |
| 节律周期的头段 | 这个周期 | 只在本周期 |
| match 分支的头段 | 被选中的分支 | 只在这次分支执行 |
| 函数参数、外部传入 | 外部创建层 | 由调用方决定，可跨多次 drive |

- 同一层按声明顺序启用，按成功启用的逆序关闭。
- 某个对象启用失败时，后面的对象不再启用，图不运行，此前成功启用的对象仍会关闭；失败的对象自己负责清理已经分配的部分。
- 一个对象关闭出错不会阻止其他对象关闭。原来的执行错误和关闭错误一起保存在 `LifecycleError` 里。
- System 只管理图里用到的本层对象，不扫描普通局部变量。`Drop` 不等于异步的 `on_shutdown`。

**传入的对象不重置。** 子 System 和子节律只使用外层传进来的对象：不重复启用，不替创建层关闭，也不会在每次 drive 时清空状态。需要重新开始时，显式创建新对象或调用重置方法。

正常执行的顺序是：执行头段构造对象 → 按声明顺序 `on_init` → 运行图，等待本次运行结束、交回对象 → 执行尾段 → 逆序 `on_shutdown`。头段在启用之前执行，所以"构造完成"不等于"已经启用"。

## 三种执行结果

```rust
pub type Execution<T> = Result<Completion<T>, RoplatError>;
pub enum Completion<T> { Completed(T), Stopped }
```

| 结果 | 含义 |
|---|---|
| `Ok(Completed(value))` | 正常完成，带业务值 |
| `Ok(Stopped)` | 合作式停止，没有业务值，但不是失败 |
| `Err(error)` | 执行失败 |

节点 Output 里的 `Result` 是业务数据，与这一层无关；`node?` 才把业务错误提升为执行失败。子节律在图里有两个结果端点：`.output` 读取正常完成的 Output，失败或停止默认向父域传播；`.outcome` 交出完整的 `Execution`，由父图显式处理。

## 失败时怎样退出

同一个域里一个分支失败后：

1. 请求同域的兄弟停止，后续工作在支持的停止点观察到请求；
2. 等待已经开始的周期和分支完整返回，交回它们用到的对象；
3. 合并结果（多个分支的错误保存在 `ParallelError` 里），由创建层关闭自己的对象。

框架不会用提前返回的 `try_join` 或丢弃 Future 来结束持有对象的工作。

## 停止的范围

- 未指定上下文的 System 调用建立自己的根停止域，不会自动继承调用者的停止范围。
- `#[roplat::system(context = ctx)]` 使用调用方的上下文；调用方保留 clone 即可请求停止。
- `ctx.clone()` 共享同一个停止域，`ctx.child()` 建立子域：父停止向下传播，子停止不影响父和兄弟。
- 停止是粘性的，新的独立运行要用新的上下文。
- 嵌套节律的每次 drive 都有自己独立的、未停止的停止作用域；上一次 drive 留下的句柄不能停止新的 drive。

## 保证的边界

合作式失败和停止保证等待在途工作、交回对象、执行创建层的关闭。以下情况不在保证内：panic、Future 被丢弃、任务被 abort、进程退出，以及不合作的无限或阻塞调用。

停止请求是软件层面的。它不会自动让设备进入安全状态，不会撤回已经发出的指令、旁路消息或状态变化，也没有硬截止时间。设备在停止时怎样保持、减速、确认，由驱动定义。

完整示例见[失败、停止与收尾](../tutorial/stop-and-failure.md)。
