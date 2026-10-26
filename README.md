# roplat-pages

[roplat](https://crates.io/crates/roplat) 的文档站源码，使用 MkDocs 与 Material for MkDocs 构建，发布在 <https://robot-exp-platform.github.io/roplat-pages/>。

> roplat 仍在快速迭代，API 不稳定。本站内容对应 roplat 0.5.0。

## 本地预览

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/mkdocs serve
```

## 检查

```sh
.venv/bin/mkdocs build --strict
python3 scripts/verify_examples.py
```

第二条命令把教程里标记的完整程序从 Markdown 中原样抽取出来，用 crates.io 上的 roplat 编译、运行，核对输出与页面一致，并运行 Clippy 与 rustfmt。需要 Rust nightly 工具链；本机已有依赖缓存时可加 `--offline`。说明见 [VALIDATION.md](VALIDATION.md)。

## 目录

| 路径 | 内容 |
|---|---|
| `docs/start/` | 安装、第一个程序、学习路线 |
| `docs/tutorial/` | 按机器人任务组织的教程，每篇一个完整程序 |
| `docs/concepts/` | 设计与原理 |
| `docs/integrate/` | C++ / Python 节点、YAML 入口、静态图 |
| `docs/reference/` | 语法速查、内置节点与节律、诊断、迁移、支持范围 |
| `docs/en/` | 英文概览 |
| `validation/` | 示例验证用的 Cargo 清单、依赖锁与最近一次验证摘要 |
| `scripts/verify_examples.py` | 示例验证脚本 |

推送到 `main` 后，GitHub Actions 会检查并部署到 GitHub Pages。
