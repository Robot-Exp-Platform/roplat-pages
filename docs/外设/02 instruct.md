# 外设篇 - 指令类型

不同的指令为外部调用，在面向对象的编程中，这通常以继承、虚函数等方法实现。在 rust 并非狭义上定义的面向对象语言，在这里通过 `trait` 来实现.

## 通用指令

=== "Rust"
    ```rust
    pub trait RobotBehavior {
        ...
    }
    ```

- `version`

获取驱动版本和机器人版本，一般来说是一样的，但是因厂商而异。如 Franka 存在[版本兼容管理](https://www.franka.cn/FCI/compatibility.html)， 系统版本、驱动版本、机器人版本应当挂钩，否则会出现指令问题。

=== "Rust"
    ```rust
    pub fn version(&self) -> String
    ```

=== "Python"
    ```python
    def version(self) -> str:
    ```

=== "C++"
    ```cpp
    std::string version()
    ```

- `init`

初始化机器人的操作，一般来说初始化完成的工作主要在于驱动和控制柜的初始化，初始化后的机器人一般是去使能的，避免突然启动导致的安全问题。

=== "Rust"
    ```rust
    pub fn init(&mut self) -> RobotResult<()>
    ```

=== "Python"
    ```python
    def init(self)
    ```

=== "C++"
    ```cpp
    void init()
    ```

- `shutdown`

关闭机器人的操作，一般来说关闭完成的工作主要在于驱动和控制柜的关闭，关闭过程中会自动对机器人去使能，但是为了安全还是建议在关闭前手动去使能。

=== "Rust"
    ```rust
    pub fn shutdown(&mut self) -> RobotResult<()>
    ```

=== "Python"
    ```python
    def shutdown(self)
    ```

=== "C++"
    ```cpp
    void shutdown()
    ```

- `enable`

使能机器人的操作，使能后的机器人会解开关节锁，此时可能会导致安全问题，使能过程的机器人一般应该保证周围空间环境的安全。使能后机器人可以进行运动操作。

=== "Rust"
    ```rust
    pub fn enable(&mut self) -> RobotResult<()>
    ```

=== "Python"
    ```python
    def enable(self)
    ```

=== "C++"
    ```cpp
    void enable()
    ```

- `disable`

去使能机器人的操作，去使能后的机器人会上锁关节，此时机器人会停止运动操作。

=== "Rust"
    ```rust
    pub fn disable(&mut self) -> RobotResult<()>
    ```

=== "Python"
    ```python
    def disable(self)
    ```

=== "C++"
    ```cpp
    void disable()
    ```

- `reset`

重置机器人的操作，重置后的机器人会回到初始状态，恢复初始状态过程中可能会导致运动安全问题，部分运动行为要求在重置后才能执行。

=== "Rust"
    ```rust
    pub fn reset(&mut self) -> RobotResult<()>
    ```

=== "Python"
    ```python
    def reset(self)
    ```

=== "C++"
    ```cpp
    void reset()
    ```

- `is_moving`

回答机器人是否在运动的问题，大多数机器人不能同时执行多个运动指令和控制指令，此时就需要判断机器人运动状态作为指令执行条件。

=== "Rust"
    ```rust
    pub fn is_moving(&mut self) -> bool
    ```

=== "Python"
    ```python
    def is_moving(self) -> bool:
    ```

=== "C++"
    ```cpp
    bool is_moving()
    ```

- `stop`

停止机器人的运动，停止后的机器人会立即停止运动，本指令并不会自动去使能

=== "Rust"
    ```rust
    pub fn stop(&mut self) -> RobotResult<()>
    ```

=== "Python"
    ```python
    def stop(self)
    ```

=== "C++"
    ```cpp
    void stop()
    ```

- `resume`

恢复运动状态，由 `stop` 指令停止后的机器人可以通过 `resume` 恢复运动，但是触发 `emergency_stop` 后的机器人需要先 `clear_emergency_stop` 才能恢复运动。

=== "Rust"
    ```rust
    pub fn resume(&mut self) -> RobotResult<()>
    ```

=== "Python"
    ```python
    def resume(self)
    ```

=== "C++"
    ```cpp
    void resume()
    ```

- `emergency_stop`

急停！急停！急停！无论是来源于主动控制还是由于机器人自身的安全保护，这都代表机器人遇见了无法处理的问题，一般来说会对机器人去使能，部分机器人会直接下电。触发急停后的机器人需要先 `clear_emergency_stop` 才能恢复运动。

=== "Rust"
    ```rust
    pub fn emergency_stop(&mut self) -> RobotResult<()>
    ```

=== "Python"
    ```python
    def emergency_stop(self)
    ```

=== "C++"
    ```cpp
    void emergency_stop()
    ```

- `clear_emergency_stop`

=== "Rust"
    ```rust
    pub fn clear_emergency_stop(&mut self) -> RobotResult<()>
    ```

=== "Python"
    ```python
    def clear_emergency_stop(self)
    ```

=== "C++"
    ```cpp
    void clear_emergency_stop()
    ```

## 实时指令

实时通信是一种权限态，在此权限态下的通信不会被系统中断，可以通过实时态下实现更快的实时通信，减少通信延迟。

- `enter_realtime`

进入实时态，进入实时态后的通信不会被系统中断，可以通过实时态下实现更快的实时通信，进入实时态时会检查系统是否具备了实时内核`is_hardware_realtime`。

=== "Rust"
    ```rust
    pub fn enter_realtime(&mut self, realtime_config: C) -> RobotResult<H>
    ```

=== "Python"
    ```python
    def enter_realtime(self, realtime_config: C) -> H:
    ```

=== "C++"
    ```cpp
    Handle enter_realtime(Config realtime_config)
    ```

- `exit_realtime`

退出实时态，退出实时态后的通信会被系统中断

=== "Rust"
    ```rust
    pub fn exit_realtime(&mut self) -> RobotResult<()>
    ```

=== "Python"
    ```python
    def exit_realtime(self)
    ```

=== "C++"
    ```cpp
    void exit_realtime()
    ```

- `read_state`

读取实时状态，当前是否处于实时态下。

=== "Rust"
    ```rust
    pub fn read_state(&self) -> S
    ```

=== "Python"
    ```python
    def read_state(self) -> S:
    ```

=== "C++"
    ```cpp
    State read_state()
    ```

- `quality_of_service`

获取当前的通信质量，简称为 QoS，通信质量是指通信的稳定性和实时性，通信质量越高，通信的稳定性和实时性越好。存在多种通信策略。

=== "Rust"
    ```rust
    pub fn quality_of_service(&self) -> f64
    ```

=== "Python"
    ```python
    def quality_of_service(self) -> f64:
    ```

=== "C++"
    ```cpp
    double quality_of_service()
    ```

- `is_hardware_realtime`

判断系统是否具备实时内核，实时内核是指具备实时通信能力的操作系统内核。

=== "Rust"
    ```rust
    pub fn is_hardware_realtime(&self) -> bool
    ```

=== "Python"
    ```python
    def is_hardware_realtime(self) -> bool:
    ```

=== "C++"
    ```cpp
    bool is_hardware_realtime()
    ```

## 机械臂指令

机械臂指令在静态类型上强行约束自由度 `N`, 在静态类型语言上会被强制约束，而在其他面向对象语言中会以类里的一个属性来约束，使用运行时断言来维护自由度。

机械臂指令要求先实现机器人指令。

=== "Rust"
    ```rust
    pub trait ArmBehavior<const N: usize>: RobotBehavior{
        ...
    }
    ```

- `move_to`

机械臂移动到目标位置，目标位置是一个枚举类型。该指令运行时会持续阻塞，直到机械臂移动到目标位置。

=== "Rust"
    ```rust
    pub enum MotionType<const N: usize> {
        Joint(#[serde_as(as = "[_; N]")] [f64; N]),
        JointVel(#[serde_as(as = "[_; N]")] [f64; N]),
        CartesianQuat(na::Isometry3<f64>),
        CartesianEuler([f64; 6]),
        CartesianVel([f64; 6]),
        Position([f64; 3]),
        PositionVel([f64; 3]),
    }
    pub fn move_to(&mut self, target: MotionType<N>) -> RobotResult<()>
    ```

=== "Python"
    ```python
    unimplemented
    ```

=== "C++"
    ```cpp
    Class MotionBase{
        ...
    }
    Class Joint: public MotionBase{
        ...
    }
    Class CartesianQuat: public MotionBase{
        ...
    }
    Class CartesianEuler: public MotionBase{
        ...
    }
    Class Position: public MotionBase{
        ...
    }
    Class PositionVel: public MotionBase{
        ...
    }
    void move_to(MotionType target)
    ```

- `move_to_async`

机械臂异步移动到目标位置，目标位置是一个枚举类型。该指令运行时不会持续阻塞，但是此时发送其他运动指令会导致运动指令冲突。

=== "Rust"
    ```rust
    pub fn move_to_async(&mut self, target: MotionType<N>) -> RobotResult<()>
    ```

=== "Python"
    ```python
    unimplemented
    ```

=== "C++"
    ```cpp
    void move_to_async(MotionType target)
    ```

- `move_rel`

机械臂相对移动，相对位置是一个枚举类型。

=== "Rust"
    ```rust
    pub fn move_rel(&mut self, rel: MotionType<N>) -> RobotResult<()>
    ```

=== "Python"
    ```python
    unimplemented
    ```

=== "C++"
    ```cpp
    void move_rel(MotionType rel)
    ```

- `move_rel_async`

机械臂异步相对移动，相对位置是一个枚举类型。

=== "Rust"
    ```rust
    pub fn move_rel_async(&mut self, rel: MotionType<N>) -> RobotResult<()>
    ```

=== "Python"
    ```python
    unimplemented
    ```

=== "C++"
    ```cpp
    void move_rel_async(MotionType rel)
    ```

- `move_path`

机械臂沿着给定轨迹移动，轨迹是一个枚举类型的数组。

=== "Rust"
    ```rust
    pub fn move_path(&mut self, path: Vec<MotionType<N>>) -> RobotResult<()>
    ```

=== "Python"
    ```python
    unimplemented
    ```

=== "C++"
    ```cpp
    void move_path(std::vector<MotionType> path)
    ```

- `move_path_from_file`

机械臂沿着给定文件中的轨迹移动，文件中的轨迹是一个枚举类型的数组。

=== "Rust"
    ```rust
    pub fn move_path_from_file(&mut self, path: &str) -> RobotResult<()>
    ```

=== "Python"
    ```python
    unimplemented
    ```

=== "C++"
    ```cpp
    void move_path_from_file(std::string path)
    ```

- `control_with`

机械臂控制，控制是一个枚举类型。

=== "Rust"
    ```rust
    pub enum ControlType<const N: usize> {
        Zero,
        Force([f64; N]),
    }
    pub fn control_with(&mut self, control: ControlType<N>) -> RobotResult<()>
    ```

=== "Python"
    ```python
    unimplemented
    ```

=== "C++"
    ```cpp
    void control_with(ControlType control)
    ```
