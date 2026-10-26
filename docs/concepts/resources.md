# 资源借用

设备需要排他访问，又要在失败和停止之后仍然可用。roplat 0.5 用一条独立于数据的借用通道表达它：资源本体由创建层持有，每次调用时把可变借用交给使用者，调用结束借用就结束。

## 声明与连接

```rust
impl Node for MovePair {
    type Resources = (Arm, Arm);
    type Input = (Goal, Goal);
    type Output = Result<(), MotionError>;

    async fn process<'call>(
        &'call mut self,
        (left_goal, right_goal): Self::Input,
        (left, right): (&'call mut Arm, &'call mut Arm),
    ) -> Self::Output {
        left.move_to(left_goal)?;
        right.move_to(right_goal)?;
        Ok(())
    }
}
```

```rust
&mut left >> pair.resources.0;
&mut right >> pair.resources.1;
left_goal >> pair.input.0;
right_goal >> pair.input.1;
```

- `type Resources = (A, B)` 对应 `process` 第三个参数 `(&mut A, &mut B)`，不是 `&mut (A, B)`。无资源写 `()`。目前最多 16 个资源槽。
- 每个资源单独连接一个槽，编号从 0 连续，单个资源也要写 `.resources.0`。同一次调用不能两次借用同一个本体。
- Rhythm 也可以声明 `Resources`，借用覆盖整次 drive；这期间它的周期域不能再使用同一个资源。

## 为什么不是消息

把设备放进 Input/Output 在节点间传递，失败路径上就要想办法把它"还回来"；漏掉一条路径，设备就丢了。借用通道让这件事由 Rust 的借用规则保证：

- 成功、业务错误、执行失败和合作式停止，都不需要通过业务 Output 归还设备。
- 右臂运动失败时，两台机械臂的本体仍由调用方持有；只是之前发给左臂的指令不会被撤回。
- 允许通过可变引用替换设备本体，框架不检查对象身份。

## 排序只看依赖

同一资源的多个使用者只按图依赖排序：数据边、`.trigger` 边，以及由它们传递形成的路径。绑定语句的书写顺序不构成顺序。任意两个使用者之间没有依赖路径时，编译报错，诊断标出两处并建议补一条 `.trigger` 边：

```rust
&mut arm >> reach.resources.0;
goal >> reach;
reach?;
&mut arm >> control.resources.0;
reach >> control.trigger;          // 同一资源的两个使用者之间必须有依赖
control.outcome >> record;
```

节律结果用 `.outcome` 处理时，写 `child.outcome >> next.trigger;` 建立依赖而不消费它。

- 内层域借用外层资源时，在外层看来整个域是一个使用者。
- 同一个 match 的不同分支互斥，各自使用同一资源不冲突。资源绑定写在调用所在的作用域：只在分支里调用的使用者，就在分支里绑定。
- 不同资源的使用者可以按图依赖并发。

## 资源不改变图的结构

相邻两个使用者之间已经有依赖路径，所以资源不会把一张串并结构的图切开，双臂同周期这类图的调度与没有资源时相同。多个节点各自借用多个资源、资源链相互交叉时，编译器在同一任务内补充先后顺序；少数仍无法保持在同一执行单元的形状，借用经零分配的交接在同一次 join 内移动，由 Rust 借用检查验证，不加锁、不复制、不 spawn。

## 生命周期

本层创建的资源由本层启用和关闭；参数传进来的资源由调用方管理。内层域借用外层资源，不重复启停。尾段可以直接调用资源的方法；参数传入的资源可以原样返回给调用方，本层创建的资源要留到关闭钩子执行，所以尾段返回状态快照。

借用保证不替代设备会话的收尾，也不回滚已经发出的指令。

## 不再使用的写法

0.4 的 `ResourceSlot`、`reclaim_input`、资源返回边，以及 `&mut arm >> user`（不写槽号）、`user >> &mut arm` 都已删除，宏会给出诊断。迁移见[从 0.4 迁移](../reference/migration.md)。
