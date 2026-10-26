# roplat-pages 写作与维护约定

本仓库是 roplat 的公开文档站，面向使用 roplat 编写机器人程序的人。仓库和站点都是公开的：只写公开可得的信息。

## 内容依据

- 以 crates.io 上已发布的 roplat 版本为准（当前 0.5.0），API 签名以 docs.rs 为准。
- 只链接公开资源：crates.io、docs.rs、本仓库、roplat-skills 等公开仓库。不写未公开仓库的链接、内部提交号、内部验收数据或内部流程。
- roplat 仍在快速迭代，API 不稳定；首页和安装页保留这条警告。
- 没有实际运行验证的内容（外语构建流程、YAML 入口、硬件、实时性能、其他平台）如实标注验证范围，不写成"已验证"。

## 写法

- 中文为主，`docs/en/` 是英文概览，不宣称已有完整翻译。
- 应用例子使用真实的 `#[roplat::system]`，不要用手写的 `process().await` 调用链替代 System 组图；节点实现 `Node::process`、节律实现 `Rhythm::drive` 是正常的扩展点。
- 教程每篇围绕一个机器人任务，给出一个可以直接复制运行的完整程序，用模拟设备代替真实机器人；断言写在调用方，不写在节点里。
- 讲清这些语义，不要写反：创建层负责生命周期；外部对象跨 drive 保留状态；Input/Output 属于整次 drive、Yield/Feed 属于每个周期；父域等子 drive 完成；业务 `Result` 是数据，`?` 才提升为失败；设备经 `.resources.N` 借用；同一实例只有一个调用位置；合作式退出的保证边界；软件停止不等于设备安全停止。
- 已知问题和限制写进 `docs/reference/scope.md`。

## 完整程序的标记

````markdown
<!-- roplat-example: name -->
```rust
// 完整的 src/main.rs
```
<!-- /roplat-example -->

<!-- roplat-output: name -->
```text
程序的标准输出
```
<!-- /roplat-output -->
````

`scripts/verify_examples.py` 抽取这些程序，以 `validation/Cargo.toml` 和 `validation/Cargo.lock` 构建运行，核对输出，并运行 Clippy `-D warnings` 与 rustfmt。修改程序后必须重新运行；输出中不要放每次运行都会变的值。

## 检查与发布

- `mkdocs build --strict` 无警告；`python3 scripts/verify_examples.py` 全部通过。
- 预览桌面与窄屏布局，核对站内链接与导航。
- 不提交 `site/`、`target/`、日志或临时文件。
- 推送到 `main` 会触发部署。合并 PR、手动部署或改变仓库访问权限需要维护者明确同意。
- 使用标准的 Material for MkDocs 包，不修改主题源码；依赖版本固定在 `requirements.txt`。
