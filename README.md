# Lock Family: harness security for AI agents

An agent harness is the program that runs a model as an agent and hands it
tools (Claude Code, Codex, lea, any MCP client); **harness security** is the
layer around it, separate from the model's own guardrails because it holds
whatever the model is talked into: the credentials and connections stay in a
Lock the agent cannot reach, and every approval is answered outside the
harness, in `lox run`, so an agent can never answer its own.

With it, an agent works on real systems: SQL databases
([locksql](https://github.com/DavidGodefroid/locksql)), RabbitMQ
([lockmq](https://github.com/DavidGodefroid/lockmq)), files
([lockfile](https://github.com/DavidGodefroid/lockfile)) and outbound HTTP(S)
([lockhttp](https://github.com/DavidGodefroid/lockhttp)), while a human keeps
control of what matters. Agents can run in
[lea](https://github.com/DavidGodefroid/lea) or on the host; the approval hub
is [lockhub](https://github.com/DavidGodefroid/lockhub), with its `lox` CLI.

What ships today:

- **`lox run`** (lockhub v0.9.0) is where a human approves, in a terminal of
  its own outside the agent. It shows every ticket and decision live, masked,
  and decides in auto mode by default: reads are approved by the rule, writes
  and DDL are asked every time, a connection is asked once per profile per
  session, a new lockhttp endpoint once per session. Shift+Tab switches to
  manual; quitting fails closed.
- **Auto mode per profile**: locksql v0.17.0 and lockmq v0.8.0 let each
  profile set its rules (`auto`, `ask` or `deny` per action); a looser rule is
  a reviewed policy loosening.
- **`lox audit`** lists every exchange the hub keeps: the masked request, the
  rule or the human that decided, the outcome.
- **A per-lock egress allowlist**: each lock but lockhttp reaches only the
  endpoints of its reviewed profile, on an internal network, with no internet,
  cloud metadata or other host port.
- **Proxy-side credential injection** (lockhttp v0.8.0, pre-release): the gate
  adds an API's credential to requests for one exact host, so the agent never
  holds it.
- **lea v0.9.0** no longer handles approvals: it runs the agents, and their
  Lock requests wait for `lox run`.

The flow: agent → Lock client → socket → Lock → masked ticket → hub →
`lox run` → signed decision → Lock → agent. The agent never talks to the hub,
and the hub never sees a query or a result in clear.

This repository is the family's one-page site, lockfamily.dev: static HTML,
CSS and vanilla JavaScript, no build step, no tracking, served by GitHub
Pages from the repository root (`CNAME`: `lockfamily.dev`), and its
installer, [`install.sh`](#installsh).

Preview locally:

```sh
python3 -m http.server -d . 8080
```

## The approval hub and the `lox` CLI

Every lock runs attached to [lockhub](https://github.com/DavidGodefroid/lockhub)
(v0.9.0): `lox run` starts the hub and each lock's console, and there is no
standalone console. The console holds the credentials and checks each
request, then sends the hub a signed ticket with the masked screen of the
request; `lox run` decides it (an auto rule, or you), and the hub signs the
decision, bound to the exact plan and naming the rule or the human that
decided. The lock runs only on that signed decision. The hub never runs a
request, never sees its results, and never sees values in clear.

### Quick start

```sh
brew trust davidgodefroid/tap                 # once: Homebrew asks you to trust a third-party tap
brew install davidgodefroid/tap/lockfamily   # or: curl -fsSL https://lockfamily.dev/install.sh | sh
cd ~/projects                                 # your project (with lea: lea's projects directory)
lox add locksql                               # one source at a time: locksql, lockmq, lockfile or lockhttp
lox run                                       # in a terminal of its own, outside the agent: approvals live here
```

Then start your agent in another terminal: `claude` (or Codex, or `lea`).

[`lox add TYPE`](https://github.com/DavidGodefroid/lockhub/blob/main/docs/lox-add.md)
sets one source up, guided and applied at once: its questions, the
launcher's `profile add`, `init claude` and `doctor`, the declaration in
`lockfamily.yaml` (created when it does not exist yet), a short review of
that lock, and the console's own questions at your terminal. A failure, an
`n` or Ctrl-C keeps nothing. Run it again for the next source.
[`lox init`](https://github.com/DavidGodefroid/lockhub/blob/main/docs/lox-init.md)
starts a project's hub alone first, if you prefer: it asks nothing, checks
Docker, cosign and the launchers, and lists the data sources the project's
files name (`.env*`, `compose*.yaml`, `config/`: hints only, never a secret).

A lock added while lea runs reaches it at lea's next start: `lea stop`, then
`lea`.

### By hand, with locksql

```sh
cd ~/projects                             # your project (with lea: lea's projects directory)
locksql init claude                       # Claude Code's files (its MCP server is `locksql mcp`)
locksql profile add --profile orders      # engine, host, TLS, where the password comes from; never the password
locksql doctor --fix --yes                # .locksql/ as lox run reads it
lox add locksql orders --profile orders   # latest signed locksql, by digest; pins the hub's image too
lox run                                   # review, start the hub and the console, then serve decisions
```

Docker and cosign are required: `lox add` and `lox run` check every image's
signature against its release workflow. On Linux the database must listen on
the Docker bridge, not only on 127.0.0.1 (`host.docker.internal` is the host's
gateway). For lea's agents, the lock names your uid (`allowed_uids: [1000]`
in `lockfamily.yaml`; `lox add` adds it when lea is installed). Any Claude
Code on the host reaches the lock through its launcher (`locksql mcp`), which
finds the nearest `.lockfamily/up.json` up from the working directory. lea
reads `.lockfamily/up.json` only at the root of its projects directory, so
with lea run `lox add` and `lox run` there.

### Commands (lox)

| Command | What it does |
|---|---|
| `lox run [--manual] [--no-start] [--no-upgrade]` | start (or reuse) the hub and the locks after a review, then show every ticket and decision live, masked, and serve decisions: auto mode by default, Shift+Tab for manual; `a` opens the audit; quitting fails closed |
| `lox add TYPE` | set one source up (locksql, lockmq, lockfile, lockhttp): its questions, the lock's profile, the declaration pinned by digest to the latest signed release, a short review, the console's questions; nothing is kept on a failure |
| `lox add TYPE INSTANCE [--version vX.Y.Z \| --image REF] [--profile P] [--hub-image REF]` | the older form: only declare a lock in `lockfamily.yaml`, pinned by digest |
| `lox init [--review] [--hub-image REF]` | start the project's hub alone: prerequisites, the data sources its files name as hints (read only, no secret), a `lockfamily.yaml` with the hub alone; it asks nothing |
| `lox add slack --team T… --channel C… --user U…` | enable the Slack facade; its tokens are asked at the terminal and kept with the hub's data, never in the workspace |
| `lox add telegram --chat ID --from ID` | enable the Telegram facade (bot token asked at the terminal) |
| `lox import [SUB…]` | merge sub-projects' `lockfamily.yaml`, keeping the strictest routing |
| `lox attach INSTANCE` | answer a lock console's start-up questions (policy, credentials) |
| `lox approve [--once]` | answer tickets in a plain terminal prompt: `y`, `n reason`, `s`, `q`; `o` (or Ctrl-O then Enter, where the terminal passes it: not on macOS) shows clear values; `r` approves an expired ticket again |
| `lox audit [show ID]` | list the hub's exchanges (ticket, masked request, decision with its rule or human, outcome), with filters, `--follow` and `--json`; `show` draws one exchange's masked plan, deciding rule, timings and signatures |
| `lox audit verify --data DIR --hub-key-file FILE [--lock INSTANCE=PATH] [--anchors FILE]` | check the hub's audit chain and every decision's signature, and optionally a lock's own log against them |
| `lox mobile pair --name NAME`, `lox mobile list`, `lox mobile revoke NAME` | pair a phone (one-time code, confirmed at the terminal), list or revoke phones |
| `lox doctor` | check the hub, the locks, keys, each lock's egress allowlist, the facade socket and the network; changes nothing |
| `lox up` | deprecated: it says to use `lox run` and only starts the hub and the locks |

The workspace commands take `--file` to name another `lockfamily.yaml`.
`lox add` and `lox import` only edit it: the next `lox run` reviews the
change with you.

### Facades and routing

`lox run` is the facade you keep open. The hub also takes decisions from
`lox approve`, Slack, Telegram and a paired phone (an installable web app the
hub serves; optional Web Push with no payload), and routes each risk class:

| Risk class | Terminal | Phone | Slack, Telegram |
|---|---|---|---|
| read, read-pii, write | yes | yes | yes, never a production ticket |
| prod-write, policy-loosen | yes | yes | no |
| unlock | yes | no | no |
| clear values | on demand, `o` (or Ctrl-O) in `lox approve` (`reveal: true`) | sealed to it (`seal_clear`) | never |

A chat facade never answers a production ticket, whatever its risk class. A
workspace's `hub.routing` can narrow this per instance, never widen it. An
auto rule's approval is accepted from the terminal facade only, and never for
a ticket that needs a human.

- **Reveal.** With `reveal: true` on a lock, the terminal can ask for a
  ticket's clear values: the lock seals them to that facade's key, which it
  pins, and the hub relays ciphertext.
- **Devices.** With `devices: true` a lock pins the paired phones, and each
  decision taken on a phone is signed by the phone itself (WebAuthn).
  `hub.mobile.require_device` lists the risk classes only a phone's signature
  may approve; `hub.mobile.seal_clear` seals clear screens to the phones. The
  phone reaches the hub through your own TLS proxy or tunnel to
  `127.0.0.1:8444` (`hub.mobile.origin`).

### `.lockfamily/lockfamily.yaml`

```yaml
version: 1
hub:
  image: ghcr.io/davidgodefroid/lockhub@sha256:…
  facades: [tty, mobile, slack]
  routing:
    orders: [tty, mobile]               # narrows an instance, never widens
  slack: {team: T0123, channel: C0123, users: [U0123]}
  mobile:
    origin: https://hub.example.ts.net
    seal_clear: true
    require_device: [prod-write]
    push: true
locks:
  orders:
    type: locksql
    image: ghcr.io/davidgodefroid/locksql@sha256:…
    profile: orders
    allowed_uids: [1000]   # id -u of the account that runs lea
    devices: true
    reveal: true
```

It lives in the workspace's `.lockfamily/`, which lea mounts read-only in its
agents. A `lockfamily.yaml` at the workspace's root (the older layout) is
still read, with a warning, while `.lockfamily/` does not exist; once
`.lockfamily/` exists, a root file is never read.
A lock's target, production flag, credentials and auto rules stay in its own
profile (`.locksql/`, `.lockmq/`, …), which `lox run` reviews and copies.
`lox run` writes `.lockfamily/up.json` for lea and the launchers and keeps the
hub's data, keys and audit log under `$XDG_STATE_HOME/lockfamily/` (default
`~/.local/state/lockfamily/`).

### lea

lea (v0.9.0) runs the agents and no longer handles approvals: it starts no
hub and shows no ticket. Keep `lox run` open in a terminal of its own; when
the projects directory declares locks and no `lox run` serves them, lea says
so as it starts, and the agents' requests wait at the hub. lea gives its
agents the locks' sockets named in `.lockfamily/up.json`, never the hub, and
mounts them when its container starts: a lock added while lea runs needs
`lea stop`, then `lea`. Host agents (any Claude Code) reach the same locks
through each lock's launcher, which reads `up.json` too. The contract is
lockhub's
[docs/lox-run.md](https://github.com/DavidGodefroid/lockhub/blob/main/docs/lox-run.md).
Current releases: lockhub v0.9.0, locksql v0.17.0, lockmq v0.8.0, lockfile
v0.8.0, lockhttp v0.8.0 (pre-release), lockkit v0.13.0, lea v0.9.0; all
before v1.

## install.sh

`install.sh`, served at <https://lockfamily.dev/install.sh>, installs the Lock
Family: the same tools, at the same versions, as the Homebrew meta formula
(`brew trust davidgodefroid/tap`, then `brew install davidgodefroid/tap/lockfamily`), into `~/.local/bin`, without
sudo and without pulling any image (each tool pulls its images, by digest, on
first use).

```sh
curl -fsSL https://lockfamily.dev/install.sh | sh
lea
lox add locksql
```

| Tool | Installed as |
|---|---|
| `lox` ([lockhub](https://github.com/DavidGodefroid/lockhub)) | `~/.local/bin/lox` |
| [`lea`](https://github.com/DavidGodefroid/lea) | the release tree in `~/.local/share/lea-install/vX.Y.Z`, linked as `~/.local/bin/lea` (as lea's own installer) |
| `locksql`, `lockmq`, `lockhttp`, `lockfile` (Linux only) | the launchers, `~/.local/bin/<tool>`, which run their release's images by digest; lockfile's seccomp profile in `~/.local/share/lockfile/` |
| `cosign` | `~/.local/bin/cosign`, only when no cosign is on your PATH (the meta formula installs it too; `lox init` and the launchers' `update` use it) |

`locklog` has no published release yet and is skipped. Docker is required:
Docker Engine (Linux) or Docker Desktop (macOS) must be installed and
running. Next step: `lox add <lock>` in your project, then `lox run` in a terminal of its own, outside the agent.

**Versions.** They come from the tap,
[DavidGodefroid/homebrew-tap](https://github.com/DavidGodefroid/homebrew-tap),
its single source of truth, which each project's release workflow bumps on
its tag: the tools that `Formula/lockfamily.rb` depends on, and in each
`Formula/<tool>.rb` the release URL for your system, its sha256 and the image
digests. The formulas are read as text, never run, and every value must match
a strict pattern.

**Verification.** The tap only says which release. For every tool, the
keyless signature of the release's `checksums.txt` must come from that
project's release workflow run for that very tag, the archive must match
`checksums.txt` and the formula, and a launcher's image digests must be the
ones cosign verifies for that tag. Everything is verified before anything is
installed. The signatures are checked with the cosign on your PATH; without
one, it downloads cosign v3.0.6, checks it against the sha256 pinned in
`install.sh`, and, once everything else is installed, installs it as
`~/.local/bin/cosign`.

**lox alone.** `--version vX.Y.Z` installs only `lox`, from that lockhub
release, as before (a downloaded cosign is then used for the check only);
offline, add `--sha256 <hash>` with a hash you trust:

```sh
curl -fsSL https://lockfamily.dev/install.sh | sh -s -- --version vX.Y.Z
```

The per-tool install scripts stay.

Tests (fake releases of every tool, fake tap, stub cosign, fake cosign download, no network): `sh tests/install_test.sh`
(`COSIGN_REAL=$(command -v cosign)` adds a real cosign check).

Logos and the lea demo come from each project's own repository.

Apache-2.0, see [LICENSE](LICENSE).
