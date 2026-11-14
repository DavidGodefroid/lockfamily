# Security model

The Lock Family is built so that whatever a model is talked into, it cannot
reach a credential, read personal data in clear, or approve its own
requests. This tab gathers the model of each piece.

## The guarantees

- **The agent never holds a credential.** Passwords, keys and tokens stay
  in a Lock's console, in an account and container the agent cannot reach.
- **Personal data stays masked.** Values come back masked before they reach
  the model; a clear value needs your approval.
- **An agent cannot approve itself.** Every approval is answered in
  `lox run`, outside the harness, and the hub signs it, bound to the exact
  plan.
- **The hub sees no value in clear.** It never runs a request and never
  sees its results.

## Where each piece is documented

| Piece | What its model covers |
|---|---|
| [The family, in short](/docs/security/safety-model/) | Networks, the hub, the console as the enforcement point, chat facades |
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
