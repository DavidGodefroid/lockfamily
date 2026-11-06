# The approval hub and the `lox` CLI

The reference for [lockhub](https://github.com/DavidGodefroid/lockhub)'s
`lox` CLI as the Lock Family uses it, moved here from this repository's
README. lockhub's own documentation is the contract:
[README](https://github.com/DavidGodefroid/lockhub#readme),
[docs/lox-run.md](https://github.com/DavidGodefroid/lockhub/blob/main/docs/lox-run.md),
[docs/lox-add.md](https://github.com/DavidGodefroid/lockhub/blob/main/docs/lox-add.md),
[docs/lox-init.md](https://github.com/DavidGodefroid/lockhub/blob/main/docs/lox-init.md);
`lox help` prints every command and flag of the `lox` you have.

Every lock runs attached to lockhub: `lox run` starts the hub and each lock's console, and there is no
standalone console. The console holds the credentials and checks each
request, then sends the hub a signed ticket with the masked screen of the
request; `lox run` decides it (an auto rule, or you), and the hub signs the
decision, bound to the exact plan and naming the rule or the human that
decided. The lock runs only on that signed decision. The hub never runs a
request, never sees its results, and never sees values in clear.

## Setting a source up

The quick start is in the [README](../README.md#quick-start).

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

## By hand, with locksql

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

## Commands (lox)

| Command | What it does |
|---|---|
| `lox run [--manual] [--theme light\|dark] [--no-start] [--no-upgrade] [--review] [-v] [--pin sha256:DIGEST] [--rotate hub\|INSTANCE\|all]` | start (or reuse) the hub and the locks after a review, then show every ticket and decision live, masked, and serve decisions: auto mode by default, Shift+Tab for manual; `a` opens the audit; quitting fails closed. `--manual` starts in manual mode; `--no-start` only serves decisions (another `lox run` started the hub and the locks); `--no-upgrade` keeps the pinned images instead of upgrading those older than this `lox`'s releases (verified with cosign); `--review` shows everything, the profiles line by line, and asks; `-v` shows cosign's and docker's own output; `--pin` sets the hub image by digest (going back to a previous hub); `--rotate` replaces a key before starting: the hub's, a lock's, or all (repeatable, or comma-separated) |
| `lox add TYPE` | set one source up (locksql, lockmq, lockfile, lockhttp): its questions, the lock's profile, the declaration pinned by digest to the latest signed release, a short review, the console's questions; nothing is kept on a failure |
| `lox add TYPE INSTANCE [--version vX.Y.Z \| --image REF] [--profile P] [--hub-image REF]` | the older form: only declare a lock in `lockfamily.yaml`, pinned by digest |
| `lox init [--review] [--hub-image REF]` | start the project's hub alone: prerequisites, the data sources its files name as hints (read only, no secret), a `lockfamily.yaml` with the hub alone; it asks nothing |
| `lox remove NAME [--purge]` | take a lock out of `lockfamily.yaml` and stop its console after one review; its profile stays unless `--purge`; a `n`, a failure or Ctrl-C keeps the lock |
| `lox vault set --address URL [--namespace NS] [--ca-file PATH]` | write the shared `vault:` block; `lox run` reviews and applies it |
| `lox add slack --team T… --channel C… --user U…` | enable the Slack facade; its tokens are asked at the terminal and kept with the hub's data, never in the workspace |
| `lox add telegram --chat ID --from ID` | enable the Telegram facade (bot token asked at the terminal) |
| `lox import [SUB…]` | merge sub-projects' `lockfamily.yaml`, keeping the strictest routing |
| `lox attach INSTANCE` | answer a lock console's start-up questions (policy, credentials) |
| `lox approve [--once]` | answer tickets in a plain terminal prompt: `y`, `n reason`, `s`, `q`; `o` (or Ctrl-O then Enter, where the terminal passes it: not on macOS) shows clear values; `r` approves an expired ticket again |
| `lox audit [show ID]` | list the hub's exchanges (ticket, masked request, decision with its rule or human, outcome), with filters, `--follow` and `--json`; `show` draws one exchange's masked plan, deciding rule, timings and signatures |
| `lox audit verify --data DIR --hub-key-file FILE [--lock INSTANCE=PATH] [--anchors FILE]` | check the hub's audit chain and every decision's signature, and optionally a lock's own log against them |
| `lox mobile pair --name NAME`, `lox mobile list`, `lox mobile revoke NAME` | pair a phone (one-time code, confirmed at the terminal), list or revoke phones |
| `lox doctor` | check the hub, the locks, keys, each lock's egress allowlist, the facade socket and the network; changes nothing |
| `lox version`, `lox help` | print the version; list every command and flag |
| `lox up` | deprecated: it says to use `lox run` and only starts the hub and the locks |

The workspace commands take `--file` to name another `lockfamily.yaml`.
`lox add TYPE INSTANCE`, `lox vault set` and `lox import` only edit it: the next `lox run` reviews the
change with you.

## Facades and routing

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

## `.lockfamily/lockfamily.yaml`

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

## lea

lea runs the agents and no longer handles approvals: it starts no
hub and shows no ticket. Keep `lox run` open in a terminal of its own; when
the projects directory declares locks and no `lox run` serves them, lea says
so as it starts, and the agents' requests wait at the hub. lea gives its
agents the locks' sockets named in `.lockfamily/up.json`, never the hub, and
mounts them when its container starts: a lock added while lea runs needs
`lea stop`, then `lea`. Host agents (any Claude Code) reach the same locks
through each lock's launcher, which reads `up.json` too. The contract is
lockhub's
[docs/lox-run.md](https://github.com/DavidGodefroid/lockhub/blob/main/docs/lox-run.md).

