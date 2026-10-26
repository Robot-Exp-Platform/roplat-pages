# roplat at a glance

!!! warning "Evolving quickly"
    roplat's API is not stable yet; any release may introduce incompatible changes, and it is not recommended for production use. This site covers **roplat 0.5.0**.

This page is a short English overview. The tutorials and references on this site are written in Chinese; there is no complete English translation yet.

roplat organises robot programs in Rust with three roles. A **Node** performs one computation or one device operation. A **Rhythm** decides how an execution domain advances: when a cycle starts, what it hands to the graph, what it gets back and when the whole run ends. A **System**, written with `#[roplat::system]`, connects them into a graph that is turned into asynchronous Rust code at compile time.

```rust
// The arm's control rhythm hands over its state each cycle;
// the domain computes a command and hands it back.
&mut arm >> control.resources.0;
control >> |state| {
    state >> planner;
    state >> servo.input.0;
    planner >> servo.input.1;
    servo
};
```

## Key ideas

- **Four boundaries.** `Input` and `Output` belong to one complete `drive` of a rhythm; `Yield` and `Feed` belong to each cycle. A parent receives a child's Output only after that drive has finished.
- **The creating layer owns the lifecycle.** Objects created in a System are initialised and shut down by it; objects passed in keep their state across drives and are never reset by the callee.
- **Devices are borrowed, not passed as messages.** `&mut arm >> user.resources.0` lends the arm for one call. Two uses of the same resource must be ordered by a data or `.trigger` dependency.
- **Cooperative exit.** Failure and stop return the objects in flight and wait for running work. Panics, aborted or dropped futures and uncooperative blocking calls are outside this guarantee, and a software stop is not a device safety action.
- **Placement.** Only independent parts of the root scope are spawned; cycles and match arms join within one task. Heavy synchronous work goes into a hard rhythm (`rhythm.hard()`, entered by a `move` domain), which runs each drive on its own thread.
- **Sidebands.** Graph edges carry same-cycle dependencies; independent domains exchange the latest values through `Latest` or ordered events through queues.

A static graph is not a hard real-time guarantee and does not prove that arbitrary programs are free of deadlocks.

## Getting started

```toml
[dependencies]
roplat = "0.5.0"
tokio = { version = "1", features = ["macros", "rt-multi-thread", "sync", "time"] }
```

The examples on this site are verified with a nightly Rust toolchain (Rust 2024 edition); a minimum supported Rust version has not been set. API documentation is on [docs.rs](https://docs.rs/roplat/0.5.0/roplat/). The licence is PolyForm Noncommercial 1.0.0.

The complete programs in the [tutorials](../start/first-system.md) are plain Rust and readable without Chinese. For AI-assisted development, see [roplat-skills](https://github.com/Robot-Exp-Platform/roplat-skills).
