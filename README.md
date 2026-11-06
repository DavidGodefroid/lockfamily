<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/banner-dark.svg">
    <img alt="Lock Family: harness security for AI agents." src="docs/assets/banner-light.svg" width="600">
  </picture>
</p>

<p align="center">
  <a href="https://github.com/DavidGodefroid/lockfamily/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/DavidGodefroid/lockfamily/actions/workflows/ci.yml/badge.svg"></a>
  <a href="LICENSE"><img alt="License: Apache 2.0" src="https://img.shields.io/badge/license-Apache%202.0-575146"></a>
</p>

<p align="center"><b>Harness security for AI agents.</b><br>
Your agent works on real systems; a Lock holds the credentials, and you approve outside its harness.</p>

<p align="center">
  <a href="#quick-start">Quick start</a> ·
  <a href="#how-it-works">How it works</a> ·
  <a href="#documentation">Docs</a> ·
  <a href="#the-lock-family">The Locks</a> ·
  <a href="https://lockfamily.dev"><strong>lockfamily.dev</strong></a>
</p>

---

The Lock Family lets any AI agent (Claude Code, Codex, Cursor, Gemini CLI,
any MCP client) work on your databases, queues, files, logs, servers and the
web. Each data source sits behind a Lock that holds the credentials and
masks the data. Reads flow; a connection, a write or anything risky waits
for you in `lox run`, a terminal outside the agent's harness.

> [!NOTE]
> Every tool is before v1. lockhttp and lockssh are pre-releases, locklog an
> early release; lockssh and locklog are not in the Homebrew tap yet.

## Why the Lock Family

- **The agent never holds a credential.** Passwords, keys and tokens stay in
  a Lock's console, in an account and container the agent cannot reach.
- **Personal data stays masked.** Values come back masked before they reach
  the model; a clear value needs your approval.
- **An agent cannot approve itself.** Every approval is answered in `lox run`,
  outside the harness, and the hub signs it, bound to the exact plan.
- **One place for every source.** One hub, one terminal and one audit log for
  all your Locks.

## Install

Docker must be installed and running. On Linux or macOS:

```sh
brew trust davidgodefroid/tap
brew install davidgodefroid/tap/lockfamily
```

This installs `lox`, lea, the Locks' launchers and cosign (Homebrew asks you
to trust a third-party tap once). Without Homebrew, the same tools go into
`~/.local/bin`, each verified with cosign
([what the installer does](docs/install.md)):

```sh
curl -fsSL https://lockfamily.dev/install.sh | sh
```

## Quick start

1. In your project, set up one source at a time:

   ```sh
   cd ~/projects/shop
   lox add locksql      # or lockmq, lockfile, lockhttp
   ```

2. In a terminal of its own, outside the agent, keep `lox run` open:
   approvals live there.

   ```sh
   lox run
   ```

3. Start your agent in another terminal (`claude`, `codex`, `gemini`, … or
   `lea`) and ask: "how many orders were placed yesterday?". `lox run` asks
   you once for the connection; reads then run masked, and each write waits
   for your `y`.

With lea, run `lox add` and `lox run` in lea's projects directory. A Lock
added while lea runs reaches its agents at lea's next start: `lea stop`,
then `lea`.

## Highlights

<table>
<tr>
<td width="50%" valign="top">

**🔑 Credentials stay in the Lock**<br>
Each Lock's console holds the password, key or token, in its own account
and container. The agent talks to a socket, never to the database.

</td>
<td width="50%" valign="top">

**🎭 Masked by default**<br>
Every value the agent sees is masked first: emails, IPs, cards, secrets.
The hub only ever sees masked screens.

</td>
</tr>
<tr>
<td valign="top">

**✍️ You sign, outside the harness**<br>
`lox run` approves reads by rule and asks you for connections, writes and
DDL. Shift+Tab switches to manual; quitting fails closed.

</td>
<td valign="top">

**📜 Every decision audited**<br>
`lox audit` lists each exchange: the masked request, the rule or human who
decided, the outcome. Each decision is signed.

</td>
</tr>
</table>

## How it works

> agent → Lock client → socket → Lock → masked ticket → hub → `lox run` →
> signed decision → Lock → agent

<p align="center">
<picture>
  <source media="(max-width: 640px) and (prefers-color-scheme: dark)" srcset="assets/flow-dark-narrow.svg">
  <source media="(max-width: 640px)" srcset="assets/flow-light-narrow.svg">
  <source media="(prefers-color-scheme: dark)" srcset="assets/flow-dark.svg">
  <img src="assets/flow-light.svg" alt="The request flow, animated: the agent and its Lock client run in the agent harness; the client reaches the lock over a socket; the lock sends a masked ticket to the hub; lox run, in your own terminal outside the harness, decides by an auto rule or asks you; the hub signs the decision and the lock runs the request only on it, then returns masked results to the agent. The agent never talks to the hub, and the hub never sees a query or a result in clear. Four scenarios loop: an auto SELECT, a connection asked once per profile, an UPDATE you approve, a DELETE you deny.">
</picture>
</p>

An agent harness is the program that runs a model as an agent and hands it
tools. **Harness security** is the layer around it: it holds whatever the
model is talked into, because every approval is answered outside the
harness.

- The agent's Lock client is an MCP server with no credential and no
  connection. It passes each request over a socket to the Lock.
- The Lock checks and masks the request, runs nothing yet, and sends the
  hub a ticket with the masked screen.
- `lox run` decides it, by an auto rule or by asking you. The hub signs the
  decision, bound to the exact plan, and the Lock runs only on it.

What ships in `lox run` today:

- **Auto mode by default.** Reads are approved by rule, writes and DDL are
  asked every time, a connection once per profile per session, a new
  lockhttp endpoint once per session.
- **Auto rules per profile** in locksql and lockmq (`auto`, `ask` or `deny`
  per action); a looser rule is a reviewed policy loosening.
- **Key rotation and hub pinning.** `lox run --rotate hub|INSTANCE|all`
  replaces a key; `lox run --pin sha256:…` sets the hub image by digest.

## Safety model

- Each Lock but lockhttp sits on an internal network, behind an egress
  allowlist: only the endpoints of its reviewed profile, no internet, cloud
  metadata or other host port.
- The hub never runs a request, never sees its results and never sees a
  value in clear. No agent reaches the hub.
- The console is the enforcement point; skills and tool descriptions only
  guide the agent. Masking is best effort.
- Chat facades (Slack, Telegram) never answer production tickets.
- Each Lock documents what the agent can see and its residual risks in its
  own `docs/security-model.md`.

## Documentation

| Doc | What it covers |
|---|---|
| [docs/lox.md](docs/lox.md) | The `lox` reference: [setting a source up by hand](docs/lox.md#by-hand-with-locksql), [every command](docs/lox.md#commands-lox), [facades and routing](docs/lox.md#facades-and-routing), [`lockfamily.yaml`](docs/lox.md#lockfamilylockfamilyyaml), [lea](docs/lox.md#lea) |
| [docs/install.md](docs/install.md) | What the installer installs, where the [versions](docs/install.md#versions) come from, how every signature and digest is [verified](docs/install.md#verification) |
| [docs/identity.md](docs/identity.md) | The family's visual identity: tokens, fonts, logos |
| [docs/design-note.md](docs/design-note.md) | Why the site looks like a signed ticket |

## The Lock Family

| Repo | What it is |
|---|---|
| [lockfamily](https://github.com/DavidGodefroid/lockfamily) | The family site ([lockfamily.dev](https://lockfamily.dev)) and `install.sh` |
| [locksql](https://github.com/DavidGodefroid/locksql) | SQL databases: the agent queries, PII comes back masked; connections and writes wait for you. |
| [lockmq](https://github.com/DavidGodefroid/lockmq) | RabbitMQ: masked queue inspection; connections, peeks and unmasked reads wait for you. |
| [lockfile](https://github.com/DavidGodefroid/lockfile) | Files (S3, SFTP, disk): the agent asks yes/no questions about files it never reads. |
| [lockhttp](https://github.com/DavidGodefroid/lockhttp) | Outbound HTTP(S): reads of trusted hosts pass; anything that sends data or reaches an unknown host waits for you. Credentials injected by the proxy, never seen by the agent. |
| [locklog](https://github.com/DavidGodefroid/locklog) | Logs: masked, bounded log search; the agent reads the logs, not the people in them. |
| [lockssh](https://github.com/DavidGodefroid/lockssh) | Commands over SSH: allow-listed commands run at once, the rest waits for you; the SSH key never leaves the console. |
| [lockhub](https://github.com/DavidGodefroid/lockhub) | The approval hub and its `lox` CLI: `lox run` approves outside the agent's harness, signs decisions, never sees values in clear. |
| [lockkit](https://github.com/DavidGodefroid/lockkit) | The shared Go core of every Lock (console, policies, masking, signed tickets, audit, MCP wiring). |
| [lea](https://github.com/DavidGodefroid/lea) | Runs many agents in containers, wired to the Locks. |

## Contributing, security, license

- **Contributing.** Issues and pull requests are welcome, in English, on the
  repository they concern.
- **Security.** Please do not open a public issue for a vulnerability: follow
  the affected repository's `SECURITY.md`, or contact the maintainer
  privately through GitHub.
- **License.** Apache-2.0, see [LICENSE](LICENSE).

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

Tests, with no network:

- `sh tests/install_test.sh`: the installer, against fake releases
  (`COSIGN_REAL=$(command -v cosign)` adds a real cosign check);
- `sh tests/readme_test.sh`: this README's links and the `lox` reference;
- `sh tests/site_test.sh`: contrast, fonts, logos and the page at 360, 768
  and 1280 px in a headless Chrome;
- `sh tests/flow_svg_test.sh`: the animated request flow is up to date,
  accessible and under 200 KB, and plays in a headless Chrome.

The logos are generated by `python3 tools/logo_svg.py`, the animated flow
(`assets/flow-*.svg`: light and dark, wide and narrow) by
`python3 tools/flow_svg.py`. The lea demo comes from lea's repository.
