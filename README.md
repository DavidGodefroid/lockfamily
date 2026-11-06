<p align="center">
  <a href="https://lockfamily.dev"><img src="assets/mark.svg" width="96" height="96" alt="Lock Family logo"></a>
</p>

<h1 align="center">Lock Family</h1>

<p align="center"><strong>Harness security for AI agents.</strong><br>
Your agent works on real systems. The credentials stay locked, and you approve outside its harness.</p>

<p align="center"><a href="https://lockfamily.dev"><strong>lockfamily.dev</strong></a></p>

An agent harness is the program that runs a model as an agent and hands it
tools (Claude Code, Codex, lea, any MCP client). **Harness security** is the
layer around it, separate from the model's own guardrails because it holds
whatever the model is talked into: the credentials and connections stay in a
Lock the agent cannot reach, and every approval is answered outside the
harness, in `lox run`, so an agent can never answer its own.

Reads come back masked and, in `lox run`'s auto mode, need no question; a
connection, a write and anything dangerous wait for you. The hub signs each
decision, bound to the exact plan, and never sees a query or a result in
clear:

> agent → Lock client → socket → Lock → masked ticket → hub → `lox run` →
> signed decision → Lock → agent

## The family

| Tool | What it does | Releases |
|---|---|---|
| [locksql](https://github.com/DavidGodefroid/locksql) | SQL databases: masked reads, each write and DDL approved | [releases](https://github.com/DavidGodefroid/locksql/releases) |
| [lockmq](https://github.com/DavidGodefroid/lockmq) | RabbitMQ: catalogue at once, message reads and dangerous actions approved | [releases](https://github.com/DavidGodefroid/lockmq/releases) |
| [lockfile](https://github.com/DavidGodefroid/lockfile) | files (Linux only) | [releases](https://github.com/DavidGodefroid/lockfile/releases) |
| [lockhttp](https://github.com/DavidGodefroid/lockhttp) | outbound HTTP(S), with credentials injected at the gate (pre-release) | [releases](https://github.com/DavidGodefroid/lockhttp/releases) |
| [lockhub](https://github.com/DavidGodefroid/lockhub) | the approval hub and its `lox` CLI: `lox add`, `lox run`, `lox audit` | [releases](https://github.com/DavidGodefroid/lockhub/releases) |
| [lea](https://github.com/DavidGodefroid/lea) | runs many agents in a container that never sees your SSH keys or private network (optional: `claude` on the host works too) | [releases](https://github.com/DavidGodefroid/lea/releases) |
| [lockkit](https://github.com/DavidGodefroid/lockkit) | the library every Lock is built on: the console, tickets, masks, audit log | [releases](https://github.com/DavidGodefroid/lockkit/releases) |

Every tool is before v1. What ships today:

- **`lox run`** is where a human approves, in a terminal of its own outside
  the agent. It shows every ticket and decision live, masked, and decides in
  auto mode by default: reads are approved by the rule, writes and DDL are
  asked every time, a connection is asked once per profile per session, a new
  lockhttp endpoint once per session. Shift+Tab switches to manual; quitting
  fails closed.
- **Auto rules per profile** in locksql and lockmq (`auto`, `ask` or `deny`
  per action); a looser rule is a reviewed policy loosening.
- **`lox audit`** lists every exchange the hub keeps: the masked request, the
  rule or the human that decided, the outcome.
- **A per-lock egress allowlist**: each lock but lockhttp reaches only the
  endpoints of its reviewed profile, on an internal network, with no
  internet, cloud metadata or other host port.
- **Key rotation and hub pinning**: `lox run --rotate hub|INSTANCE|all`
  replaces a key, `lox run --pin sha256:…` sets the hub image by digest.
- **lea** runs the agents and no longer handles approvals: their Lock
  requests wait for `lox run`.

## Quick start

Docker must be installed and running.

```sh
brew trust davidgodefroid/tap                 # once: Homebrew asks you to trust a third-party tap
brew install davidgodefroid/tap/lockfamily   # or: curl -fsSL https://lockfamily.dev/install.sh | sh
lea                                           # in the directory that holds your projects
```

Then, in another terminal, in lea's projects directory (without lea: in your
project, and start `claude` or Codex there):

```sh
lox add locksql      # one source at a time: locksql, lockmq, lockfile or lockhttp
lox run              # keep it open, outside the agent: approvals live here
```

A lock added while lea runs reaches its agents at lea's next start: `lea
stop`, then `lea`. Then ask an agent: "how many orders were placed
yesterday?". `lox run` asks you once for the connection; reads then run
masked, and each write waits for your `y`.

## Documentation

- [The `lox` reference](docs/lox.md): setting a source up
  [by hand](docs/lox.md#by-hand-with-locksql), [every command](docs/lox.md#commands-lox),
  [facades and routing](docs/lox.md#facades-and-routing),
  [`lockfamily.yaml`](docs/lox.md#lockfamilylockfamilyyaml),
  [lea](docs/lox.md#lea).
- [The installer](docs/install.md): what it installs, where the
  [versions](docs/install.md#versions) come from, and how every signature,
  checksum and image digest is [verified](docs/install.md#verification)
  before anything is installed.
- Each tool's repository documents its security model: what the agent can see
  and its residual risks.

## About this repo

This repository is the source of [lockfamily.dev](https://lockfamily.dev):
a one-page site in static HTML, CSS and vanilla JavaScript, with no build
step and no tracking, served by GitHub Pages from the repository root
(`CNAME`), and its installer, `install.sh`, served at
<https://lockfamily.dev/install.sh>.

Preview the site locally:

```sh
python3 -m http.server -d . 8080
```

Tests, with no network: `sh tests/install_test.sh` (the installer, against
fake releases; `COSIGN_REAL=$(command -v cosign)` adds a real cosign check)
and `sh tests/readme_test.sh` (this README's links and the `lox` reference).
Logos and the lea demo come from each project's own repository.

Apache-2.0, see [LICENSE](LICENSE).
