# Choose a Lock

One Lock per kind of data source. Add each one to a project with
`lox add <lock>`, then keep `lox run` open.

| Your agent needs… | Lock | What it does |
|---|---|---|
| A SQL database (PostgreSQL, MySQL, …) | [locksql](/docs/locks/locksql/) | The agent queries, PII comes back masked; connections and writes wait for you. |
| RabbitMQ | [lockmq](/docs/locks/lockmq/) | Masked queue inspection; connections, peeks and unmasked reads wait for you. |
| Files on S3, SFTP or disk | [lockfile](/docs/locks/lockfile/) | The agent asks yes/no questions about files it never reads. |
| The web or an HTTP API | [lockhttp](/docs/locks/lockhttp/) | Reads of trusted hosts pass; anything that sends data or reaches an unknown host waits for you. Credentials are injected by the proxy, never seen by the agent. |
| Logs | [locklog](/docs/locks/locklog/) | Masked, bounded log search; the agent reads the logs, not the people in them. |
| Commands on a server | [lockssh](/docs/locks/lockssh/) | Allow-listed commands run at once, the rest waits for you; the SSH key never leaves the console. |

> [!NOTE]
> lockhttp and lockssh are pre-releases, locklog an early release. lockssh
> is not in the Homebrew tap yet. The overview page of each Lock says what
> its current release supports.

## Every Lock works the same way

- **Credentials stay in the Lock.** Its console holds the password, key or
  token, in its own account and container.
- **Masked by default.** The agent sees masked values; the hub only ever
  sees masked screens.
- **You sign outside the harness.** `lox run` approves by rule or asks you.
- **Every decision is audited.** `lox audit` lists each exchange.

Each Lock documents what the agent can see and its residual risks: see
[Security](/docs/security/).
