# AGENTS.md — roplat-pages（文档站 / Documentation Site）

> **TL;DR / 一句话**
> [`roplat/`](../roplat) 项目的官方文档站，使用 mkdocs-material，中英双语，构建后部署为 GitHub Pages。
> Official documentation site for [`roplat/`](../roplat), built with mkdocs-material, bilingual (zh/en), deployed as GitHub Pages.

---

## 1. 仓库定位 / Role

* **静态网站源**——只放 Markdown 与少量资源；构建后产出 HTML。
* **不放设计提案**：那些在 [`roplat_rfc/`](../roplat_rfc)。
* **不放代码**：那些在 [`roplat/`](../roplat)。
* 与 [`roplat/`](../roplat) **强耦合**：节点/节律/系统等概念页直接引用主仓 API 名。任何主仓的破坏性 API 改动都需同步本仓。

---

## 2. 顶层布局 / Layout

```
roplat-pages/
├── mkdocs.yml              # 站点配置 + 导航树（权威）
├── yaml.schemas            # YAML schema 索引
├── assets/                 # 站点级资源（icon 等）
├── docs/                   # 文档源 ★
│   ├── index.md            # 首页
│   ├── Guide/              # 项目介绍（Why / Design / Roadmap）
│   ├── Concepts/           # 核心概念（Node / Rhythm / System / Comm / Replay）
│   ├── QuickStart/         # 上手 7 篇
│   ├── Architecture/       # 架构参考（Overview / Pipeline / CLI）
│   ├── Controbuction/      # 开发者贡献文档（spelled "Controbuction"，故意保留）
│   ├── Log/                # 开发日志（按日期 yyyy-mm-dd_topic.md）
│   ├── images/             # 图片资源
│   ├── draw/               # 架构图源（drawio）+ 导出
│   └── assets/             # 文档级资源
└── mkdocs-material/        # 主题源代码（git submodule / 分叉，本地构建用）
```

---

## 3. 导航结构（来自 [mkdocs.yml](mkdocs.yml)）/ Nav Tree

| 大区 | 子页 | 文件 | 受众 |
|---|---|---|---|
| 首页 | — | `index.md` | 所有 |
| 指南 | 项目介绍 / 设计哲学 / 学习路线 | `Guide/01–03` | 新人 |
| 核心概念 | Node / Rhythm / System / Comm / Replay | `Concepts/01–05` | 用户 |
| 快速开始 | 总览 / Rust / C++ / Python / 互通 / 编译 / 排错 | `QuickStart/00–06` | 用户 |
| 架构参考 | Overview / Pipeline / CLI | `Architecture/00–02` | 进阶用户 |
| 开发者文档 | 0 入门 / 1 设计思想 / 2 节点 / 3 节律 / 4 系统 / 5 通讯 / 6 多语言 / 7 附属文件 / 8 图规约 / 9 文件启动 / 10 启动协议 / 11 录制回放 / 12 IPC | `Controbuction/0–12` | **框架贡献者** |
| 开发日志 | 21 篇按日期 | `Log/2026-*.md` | 维护历史 |

> **注意**：`Concepts/` 下并存中英两套（如 `01 Node.md` 与 `01 节点与消息.md`），通过 mkdocs-material i18n 插件按语言切换。新增概念页要**两份都加**。

---

## 4. 与代码仓的对齐表 / Doc ↔ Code Alignment

| 文档页 | 对应主仓代码 |
|---|---|
| `Concepts/01 Node.md` | [`roplat/roplat/src/node.rs`](../roplat/roplat/src/node.rs) |
| `Concepts/02 Rhythm.md` | [`roplat/roplat/src/rhythm.rs`](../roplat/roplat/src/rhythm.rs) + [`rhythm/`](../roplat/roplat/src/rhythm/) |
| `Concepts/03 System.md` | [`roplat/roplat_system/src/system_v3/`](../roplat/roplat_system/src/system_v3/) |
| `Concepts/04 Comm.md` | [`roplat/roplat/src/comm/`](../roplat/roplat/src/comm/) |
| `Concepts/05 Replay.md` | [`roplat/roplat/src/rhythm/replay/`](../roplat/roplat/src/rhythm/replay/) |
| `Architecture/01 Pipeline.md` | `roplat_build/` + 各 crate 的 `build.rs` |
| `Architecture/02 CLI.md` | [`roplat/cargo-roplat/`](../roplat/cargo-roplat/) |
| `Controbuction/8 图规约与系统宏.md` | [`roplat/roplat_system/src/system_v3/graph.rs`](../roplat/roplat_system/src/system_v3/graph.rs) |
| `Controbuction/11 确定性录制与回放.md` | [`roplat/roplat/src/rhythm/replay/`](../roplat/roplat/src/rhythm/replay/) |
| `Controbuction/12 进程间通讯.md` | [`roplat/roplat/src/comm/ipc/`](../roplat/roplat/src/comm/ipc/) |

---

## 5. 构建与预览 / Build & Preview

```powershell
# 安装依赖（首次）
pip install -r mkdocs-material/requirements.txt
# 或者用项目级 pyproject.toml
pip install -e mkdocs-material

# 本地预览（zh + en 双站点）
mkdocs serve

# 构建
mkdocs build  # 输出到 site/

# 部署到 GitHub Pages（项目惯例）
mkdocs gh-deploy --force
```

* `mkdocs.yml::theme.name = material`，本地用 `mkdocs-material/` 子目录的主题分叉；如果只有官方版也能构建。
* i18n 配置：`docs_structure: suffix`，文件名按 `.zh.md` / `.en.md` 自动分流（实际本仓采用了**目录内并存中英文件**的方案，未用后缀）。

---

## 6. 写作约定 / Writing Conventions

### 6.1 文件名

* 用前缀数字保证导航顺序：`01 节点.md`、`02 节律.md`。
* 中文页直接用中文标题作文件名，英文页用 `XX Topic.md`。
* **不要重命名既有文件** —— mkdocs.yml 里写死了路径。

### 6.2 跨页链接

* 用相对路径：`[节点](../Concepts/01%20Node.md)`。
* 链接代码仓时用完整相对路径：`[node.rs](../../roplat/roplat/src/node.rs)`。

### 6.3 代码块

* 启用了 `content.code.copy` / `content.code.select` / `content.code.annotate`：
  ```rust
  // (1)!
  pub trait Node: Send + Sync { /* ... */ }
  ```
  注解在文档末尾用 `1.  解释...` 给出。

### 6.4 图

* drawio 源放 `docs/draw/`，导出 PNG/SVG 同名同目录。
* 复杂时序/拓扑优先用 Mermaid（mkdocs-material 内置）。

### 6.5 拼写"包袱" / Spelling Quirks

* `Controbuction` = `Contribution`（拼错了，但保留以稳定 URL）。
* 其他保留的拼写错误见各仓 AGENTS.md。

---

## 7. 开发日志 / Log Conventions

[`docs/Log/`](docs/Log/) 是**项目大事记**，按 `yyyy-mm-dd_topic.md` 命名：

* 每完成一项重大功能（一个新模块、一次架构调整）就写一篇。
* 模板：动机 / 设计 / 关键决策 / 落地代码位置 / 后续 TODO。
* 现存 21 篇覆盖 2026-04-05 至 2026-04-24（comm / multi_lang / build / replay / IPC / yaml launch 等）。
* **不要把日常进度** 写成 Log；那应该进 [`roplat/TODO.md`](../roplat/TODO.md) 或 git commit。

---

## 8. 常见任务 / Common Tasks

| 任务 | 步骤 |
|---|---|
| 增加新概念页 | 1) 写 `Concepts/06 NewTopic.md` 中英两份 2) 改 `mkdocs.yml` nav 3) `mkdocs serve` 验证 |
| 链接到主仓符号 | 用 `[Node trait](../../roplat/roplat/src/node.rs#L12)` |
| 添加 Mermaid 流程 | ` ```mermaid ` 代码块直接写 |
| 同步主仓 API 改动 | 1) 改 `Concepts/` + `Controbuction/` 对应页 2) 在 `Log/` 写一篇 yyyy-mm-dd_xxx.md |

---

## 9. 给后来 Agent 的提示 / Notes for Future Agents

1. **改文档前先读** [`roplat/TODO.md`](../roplat/TODO.md) 确认你描述的功能已实现，否则会写出"画饼"文档。
2. **不要直接改 `mkdocs-material/`** —— 那是主题分叉，改了主题升级会冲突。如需自定义，覆盖 `docs/overrides/`。
3. **中英两份必须语义一致** —— 不只是机翻；术语跟 [`roplat_rfc/`](../roplat_rfc) 的中文对译表保持一致。
4. **`Controbuction/` 与 [`roplat_rfc/docs/macro/`](../roplat_rfc/docs/macro/) 内容相近但角度不同**：本仓面向"如何贡献"（实现细节），rfc 仓面向"为何这样设计"。
5. **图必须有源** —— 只放导出 PNG 但不放 drawio 源 = 后人无法再编辑。
