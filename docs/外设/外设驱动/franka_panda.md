# 外设 - 驱动 - Franka

franka 官方驱动架构如下：
![图 0](images/franka_FCI.png)  

PC 通过 Franka Control Interface (FCI) 与机器人控制柜通信

libfranka 封装了通信层、滤波器、控制环路等内容，提供了 C++ 接口。

franka_ros 是对 franka 的 ros 封装，使得 franka 机器人可以被更好的应用在 ros 系统中。
