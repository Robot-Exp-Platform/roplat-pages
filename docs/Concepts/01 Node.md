# Node — 计算单元

Node 是 Roplat 中最基础的抽象——它代表一个**最小计算单元**，接收输入，产出输出。

## Node Trait

```rust
pub trait Node: Send + Sync {
    type Input;
    type Output;
    type Error: Into<RoplatError> + Debug + Send + Sync;

    /// 核心处理方法：每次被调用时执行一次计算
    async fn process(&mut self, input: Self::Input) -> Self::Output;

    /// 生命周期：系统启动时调用
    async fn on_init(&mut self) -> Result<(), Self::Error> {
        Ok(())
    }

    /// 生命周期：系统关闭时调用
    async fn on_shutdown(&mut self) -> Result<(), Self::Error> {
        Ok(())
    }
}
```

关键特征：

- `Send + Sync` — 节点可以在异步运行时中跨线程调度
- `async fn process` — 原生异步方法，无需 `#[async_trait]` 宏（Rust 1.75+）
- 生命周期钩子提供默认空实现，大部分节点不需要重写

## 最简示例

```rust
use roplat::node::Node;
use roplat::error::RoplatError;

struct AddOne;

impl Node for AddOne {
    type Input = i32;
    type Output = i32;
    type Error = RoplatError;

    async fn process(&mut self, input: i32) -> i32 {
        input + 1
    }
}
```

这就是一个完整的节点——接收 `i32`，返回 `i32 + 1`。没有注册、没有回调、没有全局状态。

## 带状态的节点

节点可以持有可变状态：

```rust
struct Counter {
    count: u64,
}

impl Node for Counter {
    type Input = ();
    type Output = u64;
    type Error = RoplatError;

    async fn process(&mut self, _: ()) -> u64 {
        self.count += 1;
        self.count
    }
}
```

由于节点的所有权由 Rhythm 的 `drive()` 方法管理，不存在并发访问问题——编译器保证了安全性。

## #[roplat::node] 宏

对于需要参数加载、资源绑定或状态记录的节点，使用属性宏自动生成辅助代码：

```rust
#[roplat::node]
pub struct PIDController {
    /// 参数：从 YAML 加载，自动生成 __PIDControllerParams 结构体
    #[param]
    pub kp: f64,
    #[param]
    pub ki: f64,
    #[param]
    pub kd: f64,

    /// 状态：内部可变数据
    #[state(default = 0.0)]
    integral: f64,
    #[state(default = 0.0)]
    prev_error: f64,

    /// 可记录状态：自动生成 __PIDControllerRecord 结构体
    #[state(record)]
    output_history: Vec<f64>,
}
```

宏自动生成：

| 生成物 | 用途 |
|:------|:-----|
| `__PIDControllerParams` | 参数结构体，实现 `Deserialize` |
| `__PIDControllerRecord` | 记录结构体，实现 `Serialize` |
| `Default` impl | 使用 `#[state(default)]` 指定的默认值 |

## 多语言节点（傀儡模式）

当节点逻辑用 C++ 或 Python 实现时，在 Rust 侧声明一个"傀儡"结构体：

=== "C++ 节点"

    ```rust
    #[roplat::node(
        lang = "cpp",
        input(sensor_data, SensorData),
        output(motor_cmd, MotorCommand),
    )]
    pub struct CppController {
        pub gain: f64,    // 字段值会同步到 C++ 侧
    }
    ```

    构建系统自动生成 C++ 头文件、FFI 桥接和消息类型定义。

=== "Python 节点"

    ```rust
    #[roplat::node(
        lang = "py",
        input(image, CameraFrame),
        output(detection, Detection),
    )]
    pub struct PyDetector {
        pub threshold: f64,
    }
    ```

    构建系统自动生成 Python ctypes 绑定和基类。

在 system DSL 中，多语言节点和 Rust 节点的使用方式**完全相同**：

```rust
timer_30hz >> {
    camera >> py_detector >> cpp_controller >> motor;
};
```

## 内置节点库

Roplat 提供了常用的预制节点：

### 算术运算

| 节点 | 输入 | 输出 | 说明 |
|:-----|:-----|:-----|:-----|
| `OpAdd<T>` | `(T, T)` | `T` | 加法 |
| `OpSub<T>` | `(T, T)` | `T` | 减法 |
| `OpMul<T>` | `(T, T)` | `T` | 乘法 |
| `OpSafeDiv<T>` | `(T, T)` | `T` | 安全除法（除零返回零） |
| `OpScale<T>` | `T` | `T` | 标量缩放 |
| `OpClamp<T>` | `T` | `T` | 数值钳制 |

### 滤波器

| 节点 | 说明 |
|:-----|:-----|
| `MovingAverage<T, N>` | N 点移动平均 |
| `ExponentialMA<T>` | 指数移动平均 |
| `MedianFilter<T, N>` | 中值滤波 |
| `LowPassFilter<T>` | 一阶低通 |
| `HighPassFilter<T>` | 一阶高通 |
| `BandPassFilter<T>` | 带通滤波 |
| `DeadbandFilter<T>` | 死区滤波 |

### IO

| 节点 | 说明 |
|:-----|:-----|
| `WriterNode<W>` | 通用字节写入器 |
| `StringWriterNode<W>` | 字符串写入（可选换行） |
| `DisplayWriterNode<W, T>` | `Display` 格式化输出 |
| `DebugWriterNode<W, T>` | `Debug` 格式化输出 |

### 逻辑运算

`LogicAnd`, `LogicOr`, `LogicNot`, `LogicXor`, `BitAnd<T>`, `BitOr<T>`, `ShiftLeft<T>`, `ShiftRight<T>` 等。

## 设计要点

1. **节点是纯计算** — 不关心时间、不关心连接拓扑，只做 `Input → Output` 转换
2. **生命周期由框架管理** — `on_init` / `on_shutdown` 由 Rhythm 在适当时机调用
3. **无全局状态** — 所有状态封装在节点实例中，不存在隐式共享
4. **async 是原生的** — 直接使用 Rust 原生 async fn，无额外宏开销

## 下一步

- [Rhythm 节律](02%20Rhythm.md) — 了解"什么时候"执行节点
- [System 系统](03%20System.md) — 了解"怎么连接"节点
