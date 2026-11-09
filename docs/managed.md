# Managed configuration

A company can set one policy for every machine of its fleet: a
`managed.toml` file, placed by an administrator (MDM, Ansible, a package),
that every Lock, `lox` and lea read. The user can make a rule stricter in
their own files, never looser, and no one can approve a loosening beyond it
in `lox run`: the managed file is above the human at the console.

This page is the v1 schema of `managed.toml`. Its implementation lands Lock
by Lock (lockkit first, then each Lock, `lox` and lea); a tool that does not
read the managed file yet ignores it. Deployment recipes and signing come
with [lockfamily#32](https://github.com/DavidGodefroid/lockfamily/issues/32).

## Where the file lives

One file for the whole family, with one section per tool, one fingerprint
in the audit and one signature:

| OS | Path |
|---|---|
| Linux | `/etc/lockfamily/managed.toml` |
| macOS | `/Library/Application Support/lockfamily/managed.toml` |

Windows comes when the family supports it. No environment variable or flag
moves the file in a release build: a test-only build tag does, so that a
user cannot point a tool at a looser file.

No file means no managed policy: every tool runs as today.

## Trust

- **Ownership is mandatory.** The file and its directory must be owned by
  root and writable by root only, the same check as the Locks'
  `/etc/<tool>/system.toml`. A badly owned file or directory is a refusal to
  start, never a file ignored: breaking the file must not lift the policy.
- **The signature is optional.** If `managed.toml.sigstore.json` sits next
  to the file, it is a cosign bundle verified against the company identity
  set at install time; present and invalid is a refusal to start.
  `[family] require_signature = true` makes it mandatory on the fleet.
- **Fingerprint.** The sha256 of the file's bytes is recorded with every
  approval (`approved/<key>.json`, `applied.json` in `lox`) and in the
  audit, so an action can be tied to the company policy it ran under.

Remote distribution (`managed_url`) is for v2: in v1 the administrator
places the file.

## Rule kinds

Every tool section has up to three tables:

| Table | Meaning | The user may |
|---|---|---|
| `[<tool>.bounds]` | The loosest value allowed for a field of every profile of the tool. | Set a stricter value; never a looser one. |
| `[<tool>.defaults]` | Values that replace the tool's built-in defaults. | Change them freely, within the bounds. |
| `[<tool>.profiles.<name>]` | A profile provided by the company, locked. | Use it; not redefine it. |

An **enforced** value is a bound with a single allowed value (for example
`credentials = ["vault"]`). There is no separate table for it.

### Bounds

A bound uses the name of the profile field it limits, as the tool's own
config file spells it (`tier`, `tls`, `limits.max_rows`, …). The bound is a
reference policy: lockkit compares each profile with it through the tool's
own policy diff, the one that already marks a change as loosening in the
console, and any field that would loosen the bound is a violation. Each
tool therefore keeps deciding what "looser" means for its own fields:

- an ordered value (a tier, a TLS mode, a limit) is a ceiling or a floor in
  the direction the tool's diff already uses: `tier = "write"` allows
  `read` and `write`, `tls = "verify-full"` allows only `verify-full`,
  `limits.max_rows = 10000` allows any value up to 10 000 but not
  unlimited;
- a list bound on a single-valued field is the set of allowed values:
  `credentials = ["vault", "ask"]` forbids `keychain`;
- `hosts` is a list of host patterns (`*.db.example.internal`): a profile
  whose host matches none is refused;
- a duration is clamped the way ticket lifetimes are: a longer value is a
  violation, a shorter one is fine.

A key the tool does not know is refused when the file is read, as in every
config of the family: a typo never weakens a bound silently.

### Defaults

A default replaces the built-in value of a field when neither the user's
nor the project's file sets it. It has the same names as a bound and must
itself sit within the bounds.

### Profiles

A managed profile has the same keys as a profile of the tool's own config.
It wins as a whole: a user or project profile of the same name is refused,
the reverse of today's rule where the project's profile replaces the
user's. To use a company profile with stricter settings, define a profile
of your own (a derived `extends = "<name>"` is planned for v2).

## Precedence

From the strongest to the weakest:

```
hard-coded floor (lockhttp's decide rules)
  > managed bounds and profiles
    > project file > user file
      > managed defaults > built-in defaults
```

The merged result is always checked against the bounds, whatever file a
value came from.

## Violations

- **At start**, a violation is a refusal citing the managed key, with no
  `Apply?` prompt: a human cannot approve beyond the company policy.

  ```
  blocked by company policy: locksql.bounds.tier = write (profile dev: tier = ddl)
  ```

- **While running**, the console's policy check (every 2 s) refuses a
  loosening beyond the bounds and audits it `refused-managed`: it never
  becomes pending, and `:review` shows it as not approvable. A tightening by
  the user is accepted as today.
- **When the managed file changes**, it is read again at the same check. A
  tightening applies at once (a changed connection field ends the session,
  as today); a loosening applies without asking the user, since the
  administrator decided it.

## Sections

The top level and `[family]` apply to every tool:

| Key | Type | Meaning |
|---|---|---|
| `version` | integer | Schema version: `1`. Any other value is refused. |
| `organisation` | string | Shown as `Managed by <organisation> (sha256:…)` in the consoles, `lox` and `lea doctor`. |
| `family.require_signature` | bool | The cosign bundle must be present and valid. Default `false`. |
| `family.require_confined_agent` | bool | Agents must run confined ([lockkit#133](https://github.com/DavidGodefroid/lockkit/issues/133)). Default `false`. |
| `family.vault` | table: `address` (string), `namespace` (string), `ca` (path), `required` (bool) | The Vault every Lock uses; with `required = true`, Vault is the only credential source. |

Each Lock's section has the three tables above. Their keys are the Lock's
own profile keys; the fields a company most often bounds:

| Section | Fields (profile keys) | Typical bounds |
|---|---|---|
| `[locksql]` | `engine`, `host`, `port`, `database`, `user`, `production`, `tier`, `tls`, `credentials`, `credentials_ttl`, `detectors`, `pii_rules`, `limits.*` | `tier`, `tls`, `credentials`, `credentials_ttl`, `hosts`, `limits.max_rows`, `limits.max_session` |
| `[lockmq]` | `url`, `vhosts`, `user`, `production`, `tier`, `tls`, `credentials`, `credentials_ttl`, `detectors`, `allow`, `limits.*` | `tier`, `tls`, `credentials`, `hosts`, `limits.peek_max`, `limits.read_max` |
| `[lockssh]` | `host`, `port`, `user`, `known_hosts`, `production`, `credentials`, `credentials_ttl`, `allow`, `auto`, `limits.*` | `auto` (per action), `credentials`, `hosts`, `limits.max_session` |
| `[lockfile]` | `source`, `endpoint`, `bucket`, `host`, `production`, `credentials`, `credentials_ttl`, `marketplaces`, `limits.*` | `credentials`, `hosts`, `marketplaces`, `limits.max_object_bytes` |
| `[lockhttp]` | `mode`, `rules`, `deny`, `internal_hosts`, `trusted` | `mode = "enforce"` (no `shadow`), `trusted` |
| `[locklog]` | not in v1: locklog reads the managed file in a later release | |

Each Lock's own documentation lists the exact keys and what loosens each
one, with its managed support.

Two kinds of rules are additive rather than bounded:

- **PII.** Managed PII rules and detectors are always on: the user can add
  rules, not remove or disable a managed one.
- **lockhttp rules.** Managed `deny` and `ask` rules are evaluated before
  the user's: a user `auto` or `free` rule never lifts a managed `deny` or
  `ask`. The hard-coded floor stays above both.

### `[lox]`

| Key | Type | Meaning |
|---|---|---|
| `auto_max` | table: action → `auto`, `ask` or `deny` | The loosest auto rule per action (`read`, `write`, `ddl`, `policy`, …). |
| `production_auto_max` | same | The same ceiling for production profiles. |
| `allow_no_upgrade` | bool | `false` forbids `lox run --no-upgrade`. |
| `image_min` | table: Lock → version | The oldest image `lox` may run per Lock. |
| `egress` | list of `host:port` patterns | The endpoints a Lock may reach: a Lock's egress is its reviewed profile's endpoints **∩** this list; an endpoint outside it fails the review of `lox run`. |

`lox` reads the host's managed file, includes it in the reviewed snapshot
and mounts it read-only in every Lock's container, beside its profile. The
review shows `managed: OK` or the list of violations, and refuses
`lox run` on a violation. `lox import` and `lockfamily.yaml` are checked
against the bounds too.

### `[lea]`

| Key | Type | Meaning |
|---|---|---|
| `approvals` | `required` | Approvals cannot be turned off. |
| `autoupdate` | bool | Forces lea's signed auto-update. |
| `grant_ttl_max` | duration | The longest grant. |
| `standing_grants` | bool | `false` forbids standing grants. |
| `claude_enforced` | table | Claude Code settings added to the keys lea already enforces. |
| `egress` | list of host patterns | The agents' egress is lea's own allowlist **∩** this list. |
| `git_hosts` | list of host patterns | The git hosts agents may push to. |

The `[lea]` section is read after the user's `lea.conf` and wins over it;
`lea config import` refuses whatever goes beyond it.

## Example

```toml
# /etc/lockfamily/managed.toml
version = 1
organisation = "Example Corp"

[family]
require_signature = false
require_confined_agent = true
vault = { address = "https://vault.example.com", required = true }

[locksql.bounds]
tier = "write"                       # never ddl or admin
credentials = ["vault", "ask"]       # no keychain
tls = "verify-full"
credentials_ttl = "8h"
hosts = ["*.db.example.internal"]
limits.max_rows = 10000

[locksql.defaults]
limits.statement_timeout = "30s"

[locksql.profiles.prod-erp]          # provided and locked
engine = "postgres"
host = "erp.db.example.internal"
database = "erp"
production = true
credentials = "vault"
vault_path = "database/creds/erp-readonly"

[lox]
auto_max = { read = "auto", write = "ask", ddl = "ask", policy = "ask" }
production_auto_max = { read = "ask" }
allow_no_upgrade = false
image_min = { locksql = "v0.17.1" }

[lea]
approvals = "required"
autoupdate = true
grant_ttl_max = "7d"
standing_grants = false
```

## Seeing the active policy

`lox managed show` and `<tool> managed show` print the source path, the
fingerprint, the organisation and the active rules. The consoles' welcome
screen and `lea doctor` show `Managed by <organisation> (sha256:…)`.
