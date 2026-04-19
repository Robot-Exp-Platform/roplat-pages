# 2026-04-19 系统篇实验基础设施设计

## 概述

完成了系统篇论文（T-RO 投稿）全部实验基础设施的详细设计文档，覆盖阶段二（对比基准）和阶段三（通信性能实验）。

## Exp-S1 通信性能实验

**4 个实验**：

1. **单点延迟**：4 种消息大小 (64B/1KB/64KB/1MB) × 3 种拓扑 (SPSC/SPMC/链式) × 多框架
2. **吞吐量**：最大速率饱和测试，区分 Triple Buffer 有损/Ring Buffer 无损
3. **CPU 占用**：固定频率 (1kHz/100Hz) 下的 CPU 和内存开销
4. **跨语言通信**：Rust→C++→Python 零序列化验证 vs ROS2 CDR 序列化

**产出规划**：6 张 Figure（Box Plot、CDF、吞吐量柱状图、CPU 对比、消息大小趋势线、跨语言开销）+ 2 张 Table。

## ROS2 对照基线

- 4 种拓扑：3 节点线性 / 6 节点菱形 / 30 节点流水线 / 100 节点网格
- roplat 概念 → ROS2 等价的完整映射（TripleBuffer↔QoS KEEP_LAST、RingBuffer↔QoS RELIABLE）
- FastDDS + CycloneDDS 双 DDS 实现
- intra-process / inter-process 双模式

## dora-rs 对照基线（可选）

Apache Arrow IPC 方案，Python Operator 实现。

## 统一测量框架

Python 包 `measurement`，包含：

- `format/schema.py`：S1~S6 全部实验的 CSV Schema 统一定义
- `stats/`：延迟/吞吐/抖动/轨迹一致性统计模块
- `plot/`：T-RO 论文风格绘图（Times New Roman、IEEE 栏宽、600dpi）
- `env/metadata.py`：实验环境元数据采集（硬件/软件/编译选项/git commit）
