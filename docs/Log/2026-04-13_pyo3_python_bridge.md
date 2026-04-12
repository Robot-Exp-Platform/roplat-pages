# 2026-04-13 PyO3 Python 运行时桥接

## 工作概述

将 Python 傀儡节点从存根状态推进到真实可运行：通过 PyO3 在 Rust 进程内嵌入 CPython 解释器，实现字段同步、生命周期转发和数据传递闭环。

核心结论：

- Python 路径已打通：`on_init`/`process`/`on_shutdown`/`drop` 均通过 PyO3 GIL 调用。
- chain_mixed 示例验证端到端可用（`fused=0.100`）。
- Python 节点采用**双继承**模式 `(XxxBase, Node)`，与 C++ 双类结构对称。

## 关键变更

### 1. Python 节点宏运行时代码（`roplat_macros/src/puppet.rs`）

`#[roplat::node(lang = "py")]` 在正常编译模式下生成以下运行时桥接：

**隐藏句柄**：

```rust
struct __RoplatPyNodeHandle_Xxx {
    instance: pyo3::Py<pyo3::PyAny>,
}
```

**on_init**：

1. 将 `py/` 和 `py/roplat_gen/` 插入 `sys.path`
2. `import <module>` → `getattr(ClassName)` → `call0()` 创建实例
3. 通过 `setattr` 将 Rust 侧配置字段逐一同步至 Python 实例
4. 调用 `obj.on_init()`
5. 将句柄 box 化存入 `__roplat_ptr`

**process（透明类型）**：

- 输入：`repr(C)` 结构体 → `slice::from_raw_parts` → `PyBytes` → `from_buffer_copy` → Python ctypes 结构体
- 输出：Python 返回对象 → `ctypes.addressof` + `ctypes.string_at` → 字节切片 → `ptr::copy_nonoverlapping` 回写 Rust 结构体

**process（不透明类型）**：

- 输入不透明：从 `py_bridge::take_opaque()` 线程本地总线读取 Python 对象，作为参数传入
- 输出不透明：将 Python 返回对象通过 `py_bridge::store_opaque()` 存入总线，Rust 侧返回零初始化 ZST

**on_shutdown**：

1. `call_method0("on_shutdown")` 通知 Python 侧
2. `Box::from_raw` 释放句柄

### 2. Drop 安全释放

Python 对象必须持有 GIL 才能释放。进程退出时解释器可能已终结，`Python::with_gil` 会 panic。

解决方案：

```rust
impl Drop for XxxNode {
    fn drop(&mut self) {
        let _ = std::panic::catch_unwind(AssertUnwindSafe(|| {
            Python::with_gil(|_py| {
                let _ = Box::from_raw(ptr as *mut Handle);
            });
        }));
    }
}
```

- `catch_unwind` 吞掉解释器终结后的 panic，防止 abort
- 正常路径下 `on_shutdown` 已释放句柄，`Drop` 仅作安全网

### 3. Python 用户节点双继承模式

代码生成器 (`roplat_build::NodeCodeGen`) 为 Python 节点生成：

- `roplat_gen/node.py`：`Node` ABC 基类，声明 `on_init`/`process`/`on_shutdown` 接口
- `roplat_gen/xxx_base.py`：`XxxBase` 类，包含字段默认值

用户文件采用双继承：

```python
class PyDecodeNode(PyDecodeNodeBase, Node):
    def process(self, input):
        ...
```

### 4. chain_mixed 验证

chain_mixed 运行链路 `rust → cpp(opaque) → cpp → py(opaque) → py → rust` 端到端通过：

- PyEncodeNode：transparent CppToPy → opaque PyOpaquePacket
- PyDecodeNode：opaque PyOpaquePacket → transparent PyToRust
- RustSink 收到 `fused=0.100`，数值正确

## 依赖变更

- `roplat` crate 新增 `pyo3` 重导出（`pub use pyo3`），特性 `auto-initialize` 启用嵌入式解释器
- `roplat` crate 新增 `py_bridge` 模块，提供 `store_opaque`/`take_opaque` 线程本地总线

## 验证

- `cargo run -p chain_mixed`：EXIT 0，`fused=0.100`
- `cargo test -p roplat_macros --quiet`：33/33 通过
