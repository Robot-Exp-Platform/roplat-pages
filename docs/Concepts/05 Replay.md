# 录制与回放

Roplat 的 replay 子系统用于把 rhythm domain 的输入、输出和时序记录下来，再按策略回放。

它的目标是让实验可以复现：

- 某个控制链路在第几帧出现异常？
- 多个节律域之间的全局顺序是什么？
- 只替换算法节点时，输入是否保持一致？
- benchmark 是否能在相同输入下重复运行？

## 核心概念

| 类型 | 作用 |
|---|---|
| `FrameRecord` | 一帧记录 |
| `RhythmMeta` | 节律域元信息 |
| `RlogWriter` / `RlogReader` | `.rlog` 文件读写 |
| `RecordingRhythm<R>` | 包装真实 Rhythm 并记录帧 |
| `ReplayRhythm<Y, D>` | 从记录中驱动回放 |
| `ReplayOrchestrator` | 多节律域全局顺序协调 |
| `SessionRecorder` / `SessionPlayer` | 环境变量驱动的会话门面 |

`.rlog` 使用 JSON-lines 风格，便于调试和崩溃后恢复部分记录。

## 何时使用

使用 replay：

- 论文实验和 benchmark。
- 真实机器人 bug 复现。
- 对比不同算法节点。
- 离线验证控制或感知链路。

不必使用 replay：

- 最小 demo。
- 普通 unit test。
- 没有时序复现要求的脚本。

## 当前推荐边界

当前可依赖的是 replay core API 和环境变量驱动门面。更高层的 `#[system(record = "...")]` 一类宏集成仍在演进，使用前应检查当前分支实现状态。

常见环境变量约定：

```powershell
$env:ROPLAT_RECORD = "trace.rlog"
cargo run -p hello

$env:ROPLAT_REPLAY = "trace.rlog"
cargo run -p hello
```

入口函数需要按当前 replay API 做好 `SessionRecorder` / `SessionPlayer` 接入，不能只设置环境变量就期待所有系统自动录制。

## 与 Iterator Rhythm 的区别

Iterator rhythm 适合“我已经有一串输入数据，按顺序喂给系统”。

Replay rhythm 适合“我记录了真实运行过程，现在要按记录的节律域、时序和全局顺序复现”。

简单离线数据集优先 Iterator；实验复现用 Replay。
