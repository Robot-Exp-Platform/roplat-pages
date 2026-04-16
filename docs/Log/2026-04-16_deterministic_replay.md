# 2026-04-16 确定性录制与回放系统

## 概述

实现了 RFC 0018 中设计的确定性录制/回放机制。以 Rhythm 的 drive 帧为录制单元，同时记录每帧的 Yield（输入状态）和 Feed（节点输出），支持全量回放、部分回放和 Feed 校验。

## 新增文件

| 文件 | 内容 |
|------|------|
| `rhythm/replay/mod.rs` | 模块导出 |
| `rhythm/replay/frame.rs` | `FrameRecord` + `RhythmMeta` 数据结构 |
| `rhythm/replay/rlog.rs` | `.rlog` 文件读写 |
| `rhythm/replay/recording.rs` | `RecordingRhythm<R>` 录制包装器 |
| `rhythm/replay/replay.rs` | `ReplayRhythm<Y,D>` 回放节律源 |
| `rhythm/replay/orchestrator.rs` | `ReplayOrchestrator` + `TurnToken` |
| `tests/replay_test.rs` | 12 个测试 |

## 设计决策

### 回放边界：Rhythm 的 Yield/Feed 接口

不在 Node 层做录制，而在 Rhythm 的 `drive()` 中拦截。原因：

- Node 层变更频繁（每次改算法都变），Rhythm 接口稳定
- 节点完全无感知，零侵入
- Yield 同时覆盖时间驱动和外部驱动两类节律

### 同时记录 Yield 和 Feed

旧版仅记录 Yield，在实现中发现不够：

- 外部驱动节律（EventRhythm）的 Yield 是传感器数据，必须记录
- `OutputOnly` 回放模式需要录制的 Feed 直接给下游域
- 有了 Feed 才能做回归校验

### JSON-lines 而非二进制

RFC 原始设计了二进制 .rlog 格式（固定头 + 帧流）。实现时选择 JSON-lines：

- 调试友好：`head -5 session.rlog` 直接可读
- 崩溃安全：逐行追加，不需要维护文件尾部索引
- Yield/Feed 仍用 bincode 二进制编码嵌入 JSON 的 `Vec<u8>`，兼顾大小和可读性
- 后续如需极致性能，可新增 v3 二进制格式

### 全局序号 + Notify 同步

多域全量回放时，每个域在独立 tokio task 中运行，通过 `AtomicU64` 全局序号 + `tokio::sync::Notify` 广播实现 turn-based 调度。比 barrier 方案更简单，且自然支持域数量不对称的情况。

## 新增依赖

- `bincode = "1"` — Yield/Feed 的二进制序列化

## 测试

12 个测试全部通过：

| 测试 | 覆盖内容 |
|------|---------|
| `test_recording_basic` | RecordingRhythm 包装 CountRhythm，验证 5 帧录制 |
| `test_recording_with_typed_feed` | 带类型 Feed 的序列化 |
| `test_replay_input_only` | 录制→回放 InputOnly 模式 |
| `test_replay_full_exact_match` | Full + Exact 校验通过 |
| `test_replay_full_mismatch_detected` | Feed 不匹配检测 |
| `test_replay_output_only_skips_execution` | OutputOnly 不执行节点 |
| `test_replay_rewind` | rewind 重置回放 |
| `test_rlog_write_read_roundtrip` | .rlog 读写往返 |
| `test_orchestrator_turn_order` | 多域全局序号调度验证 |
| `test_end_to_end_record_replay` | 端到端录制→全量回放 |
| `test_replay_tolerance_check` | 浮点容差校验通过 |
| `test_replay_tolerance_check_fails` | 超出容差检测 |

## 已知限制

1. 大数据量（如相机图像）未做压缩或外部引用优化
2. 跨平台浮点确定性未处理
3. Resource 跨域共享状态未录制（当前假设 Resource 仅域内使用）
4. system 宏尚未集成 `record`/`replay` 参数的自动代码生成
