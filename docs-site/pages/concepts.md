# Concepts

The family has three kinds of pieces: **Locks**, which stand in front of
your data sources; the **hub** with its `lox` CLI, where you decide; and
**lea**, which runs agents in containers. You can use the Locks with any
agent, with or without lea.

## The request flow

> agent → Lock client → socket → Lock → masked ticket → hub → `lox run` →
> signed decision → Lock → agent

1. The agent calls a tool of its **Lock client**, an MCP server with no
   credential and no connection.
2. The client passes the request over a socket to the **Lock**, which
   checks it and masks it, and runs nothing yet.
3. The Lock sends the hub a **ticket**: the masked screen of what would run.
4. **`lox run`** decides the ticket, by an auto rule or by asking you.
5. The hub **signs** the decision, bound to that exact plan. The Lock runs
   the request only on a signed approval, and returns masked results to
   the agent.

The agent never talks to the hub, and the hub never sees a query or a
result in clear.

## Words used in these docs

- **Agent harness**: the program that runs a model as an agent and hands it
  tools (Claude Code, Codex, Cursor, Gemini CLI, any MCP client). Harness
  security is the layer around it: every approval is answered outside the
  harness.
- **Lock**: a program that holds the credentials of one kind of data
  source and answers the agent's requests, masked: locksql (SQL databases),
  lockmq (RabbitMQ), lockfile (files), lockhttp (outbound HTTP), locklog
  (logs), lockssh (commands over SSH).
- **Console**: a Lock's process that holds the credentials and enforces its
  policy, in an account and a container the agent cannot reach. The console
  is the enforcement point; skills and tool descriptions only guide the
  agent.
- **Profile**: one configured target of a Lock (a database, a broker, a
  bucket, a host), with its own policy. `lox run` asks for a connection
  once per profile per session.
- **Masking**: values that could identify a person or leak a secret
  (emails, IPs, card numbers, tokens) come back masked before they reach
  the model. A clear value needs your approval. Masking is best effort:
  each Lock's security model says what it covers.
- **Ticket**: what waits for a decision: the masked request, the Lock and
  profile that asked, its class (read, write, connection…). `lox run` shows
  it to you.
- **Hub (lockhub)**: receives tickets from the Locks, has them decided by
  `lox run`, signs the decisions and keeps the audit log. It never runs a
  request and never sees a value in clear.
- **`lox`**: the host CLI of the hub. `lox init` and `lox add` set a
  project and its sources up, `lox run` serves decisions, `lox audit` lists
  them.
- **Auto mode**: `lox run`'s default. Reads are approved by rule, writes and
  DDL are asked every time, a connection once per profile per session.
  Shift+Tab switches to manual.
- **lea**: runs many agents (Claude Code by default, other providers too)
  in a container that sees one directory of your projects and none of your
  secrets, behind an egress proxy. lea wires its agents to the Locks.
- **lea deck**: the terminal you drive lea from: your agents in a column on
  the left, the selected agent's terminal on the right.
- **Control tower**: a lead agent in lea that takes your requests, starts
  dev and reviewer agents for them and reports back.
- **Allowances and grants**: in lea, the actions you let agents take
  without asking you (push, open a pull request, merge, close an issue…),
  checked by lea on every call.
- **Managed configuration**: a company-wide `managed.toml` that sets rules
  users can tighten, never loosen.

## Where the decisions happen

| Request | Decided by | Where |
|---|---|---|
| A Lock's read, write, connection | `lox run` (a rule or you) | Your terminal, outside the harness |
| A permission of a lea agent (a tool call) | You | The lea deck, or `lea approve` |
| A push, a merge, an issue closed by a lea agent | An allowance, or you | lea checks it on every call |
| A host the lea container may reach | You | `lea egress allow HOST`, on the host |

The Locks' decisions are never lea's: `lox run` decides them, deck or not.
