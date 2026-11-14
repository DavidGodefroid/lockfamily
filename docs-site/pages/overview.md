# The Lock Family docs

The Lock Family is harness security for AI agents. Your agent (Claude Code,
Codex, Cursor, Gemini CLI, any MCP client) works on your databases, queues,
files, logs, servers and the web through a **Lock** that holds the
credentials and masks the data. Reads flow; a connection, a write or
anything risky waits for you in **`lox run`**, a terminal outside the
agent's harness.

These docs cover the whole family: the Locks, the hub and its `lox` CLI,
and lea, which runs many agents in containers wired to the Locks.

## Where to start

| You want to… | Read |
|---|---|
| Try it in five minutes | [Install](/docs/install/), then [Quick start](/docs/quick-start/) |
| Understand the moving parts | [Concepts](/docs/concepts/) and [How it works](/docs/how-it-works/) |
| Pick the Lock for a data source | [Choose a Lock](/docs/choose-a-lock/) |
| Run many agents, safely, on one machine | [lea](/docs/lea/) and [lea deck](/docs/deck/) |
| Approve, deny and audit | [lox & hub](/docs/hub/) |
| Roll it out in a company | [Managed configuration](/docs/managed/) and its [deployment](/docs/managed/deployment/) |
| Know what an agent can and cannot see | [Security](/docs/security/) |

## The tabs

- **Get started**: this overview, the concepts, install and quick start,
  the one-line installer and the Homebrew tap.
- **lea**: the agent runtime: its CLI and daemon, agents in containers,
  providers, git, teams of agents and the control tower, allowances,
  configuration and troubleshooting.
- **lea deck**: the terminal you drive lea's agents from: rows, keys,
  messages, permissions, folders.
- **lox & hub**: `lox init`, `lox add`, `lox run`, and lockhub, the hub that
  signs every decision.
- **Locks**: one section per Lock: locksql, lockmq, lockfile, lockhttp,
  locklog, lockssh; and lockkit, the Go core they share.
- **Managed**: the company-wide `managed.toml`, and how to sign, deploy
  and verify it.
- **Security**: the family's model, lea's confinement and each Lock's
  security model.
- **Changelog**: every repository's changes.

## Where these pages come from

Each page is built from its repository's own documentation, on its default
branch: a Lock's README and `docs/` folder, lockhub's `docs/`, lea's README.
The link at the bottom of a page opens its source on GitHub; a fix goes
there, in a pull request on that repository. The site is rebuilt on every
change to the [lockfamily](https://github.com/DavidGodefroid/lockfamily)
repository, when another repository of the family asks for it (on a
release or a change to its docs), and every night.

> [!NOTE]
> Every tool is before v1. Commands and file formats can still change
> between minor versions: the changelog of each tool says when they do.
