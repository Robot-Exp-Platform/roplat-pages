# 2026-04-12 新手用户文档首版构建

## 工作目标

基于现有 RFC 与 roplat-pages 内容，开始构建面向零基础新人的用户文档路径，从理念到上手再到多语言实践，形成连贯阅读与实践链路。

## 输入材料

1. `roplat_rfc/docs/rfcs/0001 roplat.md`
2. `roplat_rfc/docs/rfcs/0003 node.md`
3. `roplat-pages/docs` 既有 Introduction 与 Controbuction 章节
4. 当前代码实现（Node/Rhythm/TypeBinding/two-pass/native backend）

## 产出概览

### 新增文档

1. `docs/02 新手学习路线.md`

用途：为新人提供统一阅读路径、实践步骤与常见误区。

### 重写/更新文档

1. `docs/index.md`
2. `docs/Controbuction/0 项目入门.md`
3. `docs/Controbuction/1 设计思想.md`
4. `docs/Controbuction/2 节点.md`
5. `docs/Controbuction/3 节律源.md`
6. `docs/Controbuction/4 系统.md`
7. `docs/Controbuction/5 通讯.md`
8. `docs/Controbuction/6 多语言.md`
9. `docs/Controbuction/7 附属文件生成.md`

## 关键改进点

1. 从“口号式描述”改为“学习路径 + 可执行命令 + 术语解释”。
2. 文档接口与当前代码实现对齐：
   - `Node::process` 返回 `Output`
   - `Rhythm` 与内置节律源行为
   - `TypeBinding` 语义
3. 反映最新多语言策略：
   - opaque 在 Rust 侧默认仅保留类型标记
   - 用户文件为目标语言权威实现
   - `cc` / `cmake` 双后端可切换
4. 降低新手心智负担：
   - 先跑通命令，再理解机制
   - 每章都给“下一步”和“常见误区”

## 后续建议

1. 增加“单机械臂最小控制回路”完整教程（含代码逐行解释）。
2. 增加“多语言项目模板”章节（Rust + C++ + Python 协同工程）。
3. 在 mkdocs 导航中显式配置新手路径（当前依赖文件顺序）。

## 当日补充（用户文档与开发者文档分离）

根据后续反馈，文档体系调整为两条独立路径：

1. 用户文档：`docs/User/*`，用于网页渲染和新人学习。
2. 开发者文档：`docs/Controbuction/*`，作为内部实现文档，不再作为用户入口。

新增用户文档文件：

1. `docs/User/00 用户文档总览.md`
2. `docs/User/01 快速开始.md`
3. `docs/User/02 核心概念.md`
4. `docs/User/03 第一个系统.md`
5. `docs/User/04 多语言接入.md`
6. `docs/User/05 常见问题.md`

并在 `mkdocs.yml` 增加显式 `nav`，确保网页侧优先展示用户文档路径。

## 当日补充（二次重构）

根据新增意见，用户文档结构进一步重构为两部分：

1. `docs/Concepts/*`：完备概念讲解。
2. `docs/QuickStart/*`：功能导向快速开始（从零工程、C++ 节点、Python 节点、数据互通、编译使用、路径排错）。

同时移除旧的 `docs/User/*` 页面，避免双路径并存造成理解分叉。
