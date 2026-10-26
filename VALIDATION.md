# 验证说明

本站有两类检查：站点构建和教程程序。

## 站点构建

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/mkdocs build --strict
```

`mkdocs.yml` 开启了 `strict` 和链接、锚点校验，任何缺页、坏链接或坏锚点都会让构建失败。

## 教程程序

```sh
python3 scripts/verify_examples.py            # 需要联网下载依赖
python3 scripts/verify_examples.py --offline  # 本机已有 Cargo 缓存时
```

脚本做的事：

1. 从 `docs/` 中找出所有 `<!-- roplat-example: 名称 -->` 标记的完整程序，原样写成一个临时 Cargo 项目的 `src/bin/名称.rs`。
2. 用 `validation/Cargo.toml` 和 `validation/Cargo.lock`（roplat 来自 crates.io）构建；`--locked` 保证依赖与记录一致。
3. 逐个运行；有 `<!-- roplat-output: 名称 -->` 块的程序，标准输出必须与页面完全一致。
4. 对全部程序运行 `cargo clippy -- -D warnings` 与 `cargo fmt -- --check`。

需要 Rust nightly 工具链。`--only 名称` 只检查一个程序；`--update-lock` 重新解析依赖并覆盖 `validation/Cargo.lock`（更新前请审阅变化）；`--record` 把本次摘要写入 `validation/examples.json`。

## 最近一次结果

见 [`validation/examples.json`](validation/examples.json)：roplat 0.5.0（crates.io），9 个程序全部通过运行、输出比对、Clippy 与 rustfmt。

## 范围

- 程序使用模拟设备，不连接机器人，不代表真实硬件、厂商 SDK、实时性能或其他平台的验证。
- `hard` 程序断言控制环在规划期间的最长周期间隔小于 20 ms，在负载很重的机器上可能失败。
- C++ / Python 流程、YAML 入口和静态图命令的说明没有被脚本覆盖。
