# Security model

The Lock Family is built so that an agent cannot reach a credential, read
personal data in clear, or approve its own requests. This tab gathers the
model of each piece.

## Confined and host agents

The guarantees below hold against whatever a model is talked into only for
an agent that itself runs **confined**: in lea, or in a container of its
own that cannot reach the container runtime, the family's keys or the
project's `.lockfamily/`.

An agent started on the host (Claude Code, Codex, Cursor, Gemini CLI…)
runs as you. It reaches a Lock through the Lock's launcher (`locksql mcp`),
whose client runs in a throwaway container and is served. The agent itself
can still drive Docker and reach the hub's local facade
([lockkit#207](https://github.com/DavidGodefroid/lockkit/issues/207),
[lockhub#221](https://github.com/DavidGodefroid/lockhub/issues/221)). With
a host agent, the Locks keep credentials and clear values out of its
context and stop its mistakes; they do not hold against an agent that is
compromised or turned against you. Run agents in lea for that.

## The guarantees

For a confined agent:

- **The agent never holds a credential.** Passwords, keys and tokens stay
  in a Lock's console, in an account and container the agent cannot reach.
- **Personal data stays masked.** Personal and secret values come back
  masked, best effort, before they reach the model; a clear value needs
  your approval.
- **An agent cannot approve itself.** Every approval is answered outside
  the harness: in `lox run`, or on a facade the hub routes the ticket to
  (`lox approve`, lea's deck, a paired phone, Slack or Telegram for
  non-production tickets). The hub signs it, bound to the exact plan.
- **The hub sees no value in clear.** It never runs a request and never
  sees its results.

## Where each piece is documented

| Piece | What its model covers |
|---|---|
| [The family, in short](/docs/security/safety-model/) | What holds for an agent on the host and in lea, networks, the hub, the console as the enforcement point, what the family does not protect against |
| [lockhub](/docs/security/lockhub/) | What the hub holds, signs and refuses |
| [lea](/docs/security/lea/) | The container's confinement: what an agent can read and reach, the egress proxy, a second kernel |
| [locksql](/docs/security/locksql/) | What the agent sees of a database, the PII analysis, refused constructs |
| [lockmq](/docs/security/lockmq/) | Queue inspection, peeks and unmasked reads |
| [lockfile](/docs/security/lockfile/) | Yes/no questions about files the agent never reads |
| [lockhttp](/docs/security/lockhttp/) | Outbound requests, trusted hosts, injected credentials |
| [locklog](/docs/security/locklog/) | Bounded, masked log search |
| [lockssh](/docs/security/lockssh/) | Allow-listed commands, the key kept in the console |

## Limits

Masking is best effort, and skills and tool descriptions only guide the
agent: the console enforces. Each model lists its residual risks; read the
one of the Lock you add.

## Reporting a vulnerability

Please do not open a public issue. Follow the `SECURITY.md` of the affected
repository, or contact the maintainer privately through GitHub.
