# Managed configuration

A company can set one policy for every machine of its fleet: a
`managed.toml` file, placed by an administrator (Ansible, a package, an
MDM), that every Lock and `lox` read. The user can make a rule stricter in
their own files, never looser, and no one can approve a loosening beyond it
in `lox run`: the managed file is above the human at the console.

This page is for the administrator who writes, signs and deploys that file.
It needs no code reading: every key, every refusal line and every command
below is the released tools' own.

| Tool | First release that applies its section |
|---|---|
| locksql | v0.18.0 |
| lockmq | v0.9.0 |
| lockfile | v0.9.0 |
| lockhttp | v0.9.0 (v0.9.1 mounts the directory in every container) |
| lockssh | v0.2.0 |
| locklog | v0.3.0 |
| lox | v0.11.0 |
| lea | the next release ([lea#399](https://github.com/DavidGodefroid/lea/issues/399)) |

An older release ignores the file: see [older tools](#older-tools).

- [Where the file lives](#where-the-file-lives)
- [Trust](#trust)
- [Fail closed](#fail-closed)
- [Rule kinds](#rule-kinds) and [precedence](#precedence)
- [Violations](#violations)
- [Sections](#sections): [top level and `[family]`](#top-level-and-family),
  [`[locksql]`](#locksql), [`[lockmq]`](#lockmq), [`[lockssh]`](#lockssh),
  [`[lockfile]`](#lockfile), [`[lockhttp]`](#lockhttp),
  [`[locklog]`](#locklog), [`[lox]`](#lox), [`[lea]`](#lea)
- [Example](#example)
- [Commands](#commands)
- [Signing](#signing)
- [Deploying](#deploying): [Ansible](#ansible),
  [Debian and rpm packages](#debian-and-rpm-packages), [macOS](#macos)
- [Verifying a deployment](#verifying-a-deployment)
- [Troubleshooting](#troubleshooting)

The recipes and the example are in [`examples/managed/`](../examples/managed/).

## Where the file lives

One directory for the whole family, with one section per tool, one
fingerprint in the audit and one signature:

| OS | Directory |
|---|---|
| Linux | `/etc/lockfamily/` |
| macOS | `/Library/Application Support/lockfamily/` |

| File | Who writes it | Meaning |
|---|---|---|
| `managed.toml` | the administrator | The policy: `/etc/lockfamily/managed.toml`, `/Library/Application Support/lockfamily/managed.toml`. |
| `signer.toml` | the administrator, when signing | The company identity the signature is checked against ([signing](#signing)). |
| `managed.toml.sigstore.json` | the administrator, when signing | The cosign bundle of `managed.toml`. |
| `managed.toml.verified` | `lox`, never the administrator | Written in the Locks' containers only: see [Locks in containers](#locks-in-containers). |

Windows comes when the family supports it. No environment variable or flag
moves the file in a release build, so that a user cannot point a tool at a
looser file. No file means no managed policy: every tool runs as without
this page.

### Locks in containers

`lox run` reads the host's file and copies it into a volume mounted
read-only at `/etc/lockfamily` in every Lock's container, whatever the host
OS, beside the Lock's profile. When the file is signed, `lox` checks the
signature on the host (a container has neither cosign nor the network for
it) and adds `signer.toml`, the bundle and `managed.toml.verified`, a stamp
of the three files the Lock trusts instead of calling cosign. Each Lock's
own launcher (`locksql`, `lockmq`, … run outside `lox`) mounts the host
directory read-only at the same place.

## Trust

- **Ownership is mandatory.** `managed.toml`, `signer.toml` and their
  directory must be owned by root (uid 0) and writable by root only (no
  group or other write bit). The file must be a regular file: a symbolic
  link is refused. A badly owned file or directory is a refusal to start,
  never a file ignored: breaking the file must not lift the policy.
- **The signature is optional.** When `managed.toml.sigstore.json` sits
  next to the file, it is verified with cosign against the identity in
  `signer.toml`; present and invalid is a refusal to start. Only keyless
  signing is supported, and `cosign` must be on the host's `PATH`.
  `[family] require_signature = true` makes the bundle mandatory.
- **Fingerprint.** The sha256 of the file's bytes is recorded with every
  approval (`managed_sha256` in the console's approved policy,
  `managed_fingerprint` in `lox`'s `applied.json`) and in every audit
  record, so an action can be tied to the company policy it ran under.
- **No secrets.** A key that looks like a secret (`token`, `password`, …) is
  refused: the file is readable by every user of the machine.

Remote distribution (`managed_url`) is for v2: in v1 the administrator
places the file.

## Fail closed

A managed file that is present but not valid is a refusal to start, never
a file or a key dropped. Each of these refuses:

- a file that is not valid TOML;
- `version` missing or other than `1`;
- an unknown top-level section, or an unknown key in `[family]` or in the
  tool's own section;
- a value of the wrong type or out of its range (a string for a bool, a bad
  duration, an unknown tier or TLS mode);
- a default outside the bounds;
- a managed profile that itself violates the bounds.

While a console runs, it reads the file again at every policy check (2 s):
a file that becomes unreadable or invalid ends its session.

### Strictness per section

Every tool checks the top level, `[family]`, and that every top-level
section names a tool of the family: `locksql`, `lockmq`, `lockssh`,
`lockfile`, `lockhttp`, `locklog`, `lox`, `lea`. It decodes only its own
section strictly: a typo in `[lockmq.bounds]` makes lockmq refuse to start,
not locksql. A Lock's section may only hold `bounds`, `defaults` and
`profiles`.

### Older tools

A release that predates managed support does not read the file at all and
runs on the user's files alone. To keep such releases off the fleet, set
[`[lox] image_min`](#lox) to the first managed release of each Lock (the
table at the top of this page): `lox` then refuses to run an older image.
An image too old to have `managed check` is not started when the file has a
section for it: `locksql v0.17.2 predates managed support: upgrade it or
set [lox] image_min`.

## Rule kinds

Every Lock's section has up to three tables:

| Table | Meaning | The user may |
|---|---|---|
| `[<tool>.bounds]` | The loosest value allowed for a field of every profile of the tool. | Set a stricter value; never a looser one. |
| `[<tool>.defaults]` | Values that replace the tool's built-in defaults. | Change them freely, within the bounds. |
| `[<tool>.profiles.<name>]` | A profile provided by the company, locked. | Use it; not redefine it. |

An **enforced** value is a bound with a single allowed value (for example
`credentials = ["vault"]`). There is no separate table for it.

### Bounds

A bound uses the name of the profile field it limits, as the tool's own
config file spells it. The Lock compares each profile with the bounds
through its own policy diff, the one that already marks a change as
loosening in the console, so each Lock decides what "looser" means for its
fields. The kinds that recur:

- **ceiling**: an ordered value (a tier, a limit, a duration) may be lower,
  not higher. `tier = "write"` allows `read` and `write`. A duration or a
  size beyond its bound is refused, never shortened silently; a bounded
  field left unset is often looser (`credentials_ttl` unset means the whole
  session, beyond any bound);
- **floor**: the reverse (`tls`, `limits.k_anonymity`): `tls =
  "verify-full"` allows only `verify-full`;
- **allowed list**: the profile's value must be in the list
  (`credentials = ["vault", "ask"]` forbids `keychain`); `hosts` is a list
  of host patterns (`*.db.example.internal`);
- **required list**: every entry must be in the profile (lockhttp `deny`,
  `detectors`);
- **additive rules**: managed PII masks and detectors are added to every
  profile; the user can add rules, not remove one, and a user allow rule
  that would show what a managed mask hides is refused.

### Defaults

A default replaces the built-in value of a field when neither the user's
nor the project's file sets it. It has the same names as a profile key and
must itself sit within the bounds.

### Profiles

A managed profile has the same keys as a profile of the tool's own config,
and the managed defaults fill what it leaves unset. It wins as a whole: a
user or project profile of the same name is refused (`managed: profile
"prod-erp" is provided by the company's managed configuration and cannot be
redefined in the project config: rename yours`). To use a company profile
with stricter settings, define a profile of your own.

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

A violation names the managed key, the bound, the profile and its value,
in one of these forms:

```
blocked by company policy: <key> = <bound> (profile <p>: <field> = <value>)
blocked by company policy: <key> does not allow <value> (profile <p>: <field> + <value>)
blocked by company policy: <key> requires <value> (profile <p>: <field> - <value>)
```

For example, from the released tools on the [example](#example):

```
blocked by company policy: locksql.bounds.tier = write (profile dev: tier = ddl)
blocked by company policy: lockmq.bounds.hosts = *.mq.example.internal (profile dev: url = rabbitmq.dev.example.org)
blocked by company policy: lockssh.bounds.exec = false (profile dev: exec = true)
blocked by company policy: lockfile.bounds.max_object_bytes = 10485760 (profile docs: limits.max_object_bytes = 52428800)
blocked by company policy: lockhttp.bounds.trusted does not allow github.com (profile default: trusted + github.com)
blocked by company policy: lockhttp.bounds.deny requires pastebin.com (profile default: deny - pastebin.com)
blocked by company policy: locklog.bounds.kinds does not allow sources.system.kind = journald (profile staging; allowed: file, loki)
blocked by company policy: family.vault.required = true (profile dev: credentials = ask)
```

- **At start**, a violation is a refusal with no `Apply?` prompt, audited
  `refused-managed`: a human cannot approve beyond the company policy. The
  console exits 3.
- **While running**, the console's policy check (every 2 s) refuses a
  loosening beyond the bounds and audits it `refused-managed`: it never
  becomes pending, and `:review` shows it as not approvable. A tightening by
  the user is accepted as today.
- **When the managed file changes**, it is read again at the same check
  and audited `managed-changed`. A policy in force beyond the new bounds is
  replaced at once by the files' policy when that one is within them (a
  changed connection field ends the session, as any tightening), else the
  session ends. In `lox run`, a change of the managed file alone recreates
  the Locks without an `Apply?` question: the administrator decided it.
- **In `lox run`**, each Lock's `managed check` runs on its reviewed
  profile before the Lock starts. A Lock beyond the bounds is not started,
  the others are: `lock crm: not started: blocked by company policy:
  locksql.bounds.tier = write (profile p: tier = ddl) (the other locks
  are)`.

## Sections

### Top level and `[family]`

These apply to every tool:

| Key | Type | Meaning |
|---|---|---|
| `version` | integer | Schema version: `1`. Missing or any other value is refused. |
| `organisation` | string, printable, 128 bytes at most | Shown as `Managed by <organisation> (sha256:…)` in the consoles, `lox run`'s header and `lox doctor`. |
| `family.require_signature` | bool | The cosign bundle must be present and valid. Default `false`. |
| `family.require_confined_agent` | bool | Agents must run confined ([lockkit#133](https://github.com/DavidGodefroid/lockkit/issues/133)). Accepted; no released tool enforces it yet. Default `false`. |
| `family.vault.address` | string | The Vault every Lock uses: `lox` puts it in place of `lockfamily.yaml`'s `vault:` for the Locks with `vault: true`. |
| `family.vault.namespace` | string | Its namespace. |
| `family.vault.ca` | path | Its CA bundle. |
| `family.vault.required` | bool | Vault is the only credential source: every Lock acts as if its bounds said `credentials = ["vault"]`, cited `family.vault.required` (not for SQLite, a local file source or lockhttp, which holds no credentials). |

### `[locksql]`

`[locksql.bounds]`:

| Key | Type | Looser (refused) |
|---|---|---|
| `production` | `true` only | a profile with `production = false` |
| `tier` | `read`, `write`, `ddl`, `admin`: ceiling | a higher tier |
| `tls` | `disable` < `prefer` < `require` < `verify-ca` < `verify-full`: floor | a weaker mode (not applied to SQLite) |
| `credentials` | allowed list of `ask`, `keychain`, `vault` | another mode |
| `engine` | allowed list of `mariadb`, `mysql`, `postgres`, `sqlite` | another engine |
| `hosts` | host patterns, case-insensitive | a `host` or `ssh.host` no pattern matches |
| `write_functions` | `"allowlist"` only | the denylist |
| `credentials_ttl` | duration, at least `1m`: ceiling | longer, or unset |
| `auto.<action>` (`connect`, `read`, `write`, `ddl`, `unmask`) | `deny` < `ask` < `auto`: ceiling | a looser auto rule |
| `limits.statement_timeout`, `limits.max_rows`, `limits.max_cell_chars`, `limits.max_output_bytes`, `limits.explain_rows_refuse` | ceiling (integers at least 1) | higher, or 0 (unlimited) |
| `limits.k_anonymity` | floor | lower |
| `limits.idle_timeout`, `limits.max_session` | duration: ceiling | longer |
| `limits.grant_max_duration` | duration, or `0` (grants off): ceiling | longer |
| `limits.grant_max_statements`, `limits.grant_max_rows`, `limits.grant_max_bytes` | ceiling | larger |
| `detectors` | required set of `email`, `phone`, `phone_loose`, `iban`, `card`, `be_niss`, `fr_nir`, `nl_bsn`, `us_ssn` | nothing: added to every profile |
| `[[locksql.bounds.pii_mask]]` | `column` (`db.table.column` pattern), `mode` (`redact` default, `partial`, `email`) | nothing: masked in every profile, whatever its `pii_rules` |

`[locksql.defaults]` and `[locksql.profiles.<name>]` take the profile keys
of locksql's [configuration](https://github.com/DavidGodefroid/locksql/blob/main/docs/configuration.md#managed-configuration),
`limits.*` included.

### `[lockmq]`

`[lockmq.bounds]`:

| Key | Type | Looser (refused) |
|---|---|---|
| `production` | `true` only | a profile with `production = false` |
| `tier` | `read` < `peek`: ceiling | `peek` under `read` |
| `tls` | floor, as locksql | a weaker mode |
| `body_mode` | `"redact-unknown"` only | `detect` |
| `vhosts` | allowed list | a vhost outside the list, or no `vhosts` (every vhost) |
| `credentials` | allowed list of `ask`, `keychain`, `vault` | another mode |
| `hosts` | host patterns | a host of `url`, `amqp_url`, `stream_url` or `ssh.host` no pattern matches |
| `credentials_ttl` | duration, at least `1m`: ceiling | longer, or unset |
| `auto.<action>` (`connect`, `list`, `read`, `peek`, `get`, `publish`, `purge`, `delete`) | `deny` < `ask` < `auto`: ceiling | a looser auto rule |
| `limits.read_max`, `limits.peek_max`, `limits.max_body_bytes`, `limits.max_output_bytes`, `limits.list_page_size` | ceiling, at least 1 (the built-in default counts when the profile sets none) | larger |
| `limits.request_timeout`, `limits.idle_timeout`, `limits.max_session` | duration: ceiling | longer |
| `detectors` | required set | nothing: added to every profile |
| `[[lockmq.bounds.pii_mask]]` | as `[[mask]]` in `pii.toml`: `queue` or `exchange` (vhost/name globs), one of `body` (JSON path), `header` or `property`, and `mode` | nothing: masked in every profile |

`[lockmq.defaults]` and `[lockmq.profiles.<name>]` take the profile keys of
lockmq's [configuration](https://github.com/DavidGodefroid/lockmq/blob/main/docs/configuration.md#managed-configuration).

### `[lockssh]`

`[lockssh.bounds]`:

| Key | Type | Looser (refused) |
|---|---|---|
| `production` | `true` only | a profile with `production = false` |
| `hosts` | host name patterns (`*`, `?`, `[...]`) | a `host` no pattern matches |
| `known_hosts` | path, enforced | any other `known_hosts`, the default one included |
| `auth` | allowed list of `key`, `password` | another `auth` |
| `credentials` | allowed list of `none`, `ask`, `keychain`, `vault` | another mode |
| `exec` | `false` only | `exec = true` |
| `allow` | allowed list of rules | an allow rule not in the list |
| `auto.<action>` (`connect`, `run`, `exec`, `unmask`) | `deny` < `ask` < `auto`: ceiling; a preset (`"full-auto"`) is refused here | a looser auto rule |
| `credentials_ttl` | duration: ceiling | longer, or unset |
| `limits.max_output_bytes`, `limits.request_timeout` | ceiling | larger |
| `limits.idle_timeout`, `limits.max_session` | duration: ceiling | longer |
| `detectors` | required set | nothing: added to every profile |
| `[[lockssh.bounds.pii_mask]]` | `pattern` (RE2), as `[[mask]]` in `pii.toml`; 200 rules of 512 bytes at most | nothing: masked in every output |

`[lockssh.defaults]` and `[lockssh.profiles.<name>]` take the profile keys
of lockssh's [usage](https://github.com/DavidGodefroid/lockssh/blob/main/docs/usage.md),
`limits.*` and `auto` included ([lockssh's managed keys](https://github.com/DavidGodefroid/lockssh/blob/main/docs/configuration.md#managed-configuration)).

### `[lockfile]`

lockfile's limits are flat keys, as in its config file. `[lockfile.bounds]`:

| Key | Type | Looser (refused) |
|---|---|---|
| `production` | `true` only | a profile without `production = true` |
| `source` | allowed list of `s3`, `sftp`, `local` | another source kind |
| `hosts` | host patterns (`*` matches any part, case-insensitive) | an s3 `endpoint` host, the AWS host of a `region` (`s3.<region>.amazonaws.com`) or an sftp `host` no pattern matches |
| `buckets` | allowed list of s3 bucket names | another bucket |
| `credentials` | allowed list of `ask`, `keychain`, `vault`, `none` | another mode (a local source's is `none`) |
| `credentials_ttl` | duration: ceiling | longer, or unset |
| `idle_timeout`, `max_session`, `handle_ttl` | duration: ceiling | longer |
| `max_object_bytes`, `max_workspace_bytes` | size: ceiling | larger |
| `max_objects_per_plan`, `max_plugins_per_handle` | ceiling | larger |
| `answer_quantum` | duration: floor | shorter |
| `marketplaces` | allowed list of marketplace names (`official` is lockfile's own) | a `[[marketplaces]]` entry not in the list |

`[lockfile.defaults]` takes the profile keys plus `max_workspace_bytes`;
`[lockfile.profiles.<name>]` takes exactly the profile keys of lockfile's
[configuration](https://github.com/DavidGodefroid/lockfile/blob/main/docs/configuration.md#managed-configuration).
lockfile has no PII rule to add.

### `[lockhttp]`

`[lockhttp.bounds]`:

| Key | Type | Looser (refused) |
|---|---|---|
| `production` | `true` only | not a production profile |
| `mode` | `"enforce"` only | `shadow` mode |
| `heuristics` | `off` < `shadow` < `enforce`: floor (`shadow` or `enforce`) | lower heuristics |
| `buffer_limit` | size: ceiling | larger |
| `connect_grant`, `idle_timeout`, `max_session` | duration: ceiling | longer |
| `trusted`, `splice`, `redirect_cdn` | allowed list (`api.example.com` is within `*.example.com`; both sides of `origin>cdn` are checked); an empty list allows none | an entry outside the list |
| `internal_hosts` | allowed list of `{ host, ports, read }` | a host, a port, or `read = true` the list does not allow |
| `deny` | required list | an entry of the list missing from the profile's `deny` |
| `[[lockhttp.bounds.rules]]` | managed rules: `id`, `verdict` (`deny` or `ask` only), and `container`, `agent`, `host`, `methods`, `path`, `max_body`, `expires`, `note` | removing or changing one |

`hold` and `inject` cannot be bounded: either key in `[lockhttp.bounds]` is
refused. Managed rules are evaluated above the user's:

- a managed `deny` is refused like the deny list: no rule, grant or shadow
  mode lifts it;
- a managed `ask` makes a request that would pass, or that `auto` mode
  could answer, wait for a human; a stricter decision stands (a user
  `deny`, the floor);
- at the domain (a CONNECT not decrypted), a managed rule with `methods` or
  a `path` asks, since the gate cannot see the requests the tunnel carries.

`[lockhttp.defaults]` takes `mode`, `heuristics`, `buffer_limit`, `hold`
(5m at most), `connect_grant`, `idle_timeout`, `max_session` and
`production`. `[lockhttp.profiles.<name>]` takes the keys of a
`[profiles.<name>]` table of lockhttp's
[configuration](https://github.com/DavidGodefroid/lockhttp/blob/main/docs/configuration.md#managed-configuration).
`[family] vault` has no effect on lockhttp.

### `[locklog]`

`[locklog.bounds]`; a scalar bound takes only the value shown:

| Key | Type | Looser (refused) |
|---|---|---|
| `production` | `true` only | a profile with `production = false` |
| `structured` | `"redact-unknown"` only | `detect` |
| `text` | `"template"` only | `detect` |
| `unmask` | `"never"` only | `approved` |
| `lookup` | `"approved"` only | another lookup mode |
| `strict` | `true` only | `strict = false` |
| `prefilter` | `false` only | `prefilter = true` |
| `user_journals` | `false` only | `user_journals = true` |
| `pseudonym_rotation` | `"session"`, `"never"` or a duration (`"7d"`) | a longer rotation |
| `pseudonym_max_age` | duration: ceiling | longer |
| `auto.<action>` (`read`, `unmask`, `lookup`) | `deny` < `ask` < `auto`: ceiling; a preset is refused here | a looser auto rule |
| `limits.max_records`, `limits.max_output`, `limits.lookups_per_hour`, `limits.lookups_per_hour_per_uid`, `limits.pii_adds_per_hour`, `limits.pii_rules_max`, `limits.max_calls` | ceiling | larger |
| `limits.idle_timeout`, `limits.max_session` | duration: ceiling | longer |
| `limits.local.*`, `limits.remote.*` (`range`, `count_range`, `max_bytes`, `bytes_per_hour`; remote only: `metric_queries_per_hour`, `requests_per_minute`) | ceiling | larger |
| `kinds` | allowed list of source kinds | a source of another kind |
| `hosts` | host patterns | a remote source's `url` host no pattern matches |
| `paths` | allowed absolute directories | a file source outside them |
| `auth` | allowed list of `none`, `basic`, `bearer`, `mtls`, `apikey` | another `auth` |
| `credentials` | allowed list of `ask`, `vault` | another mode |
| `tls` | floor, as locksql | a weaker mode |
| `network`, `extra_roots` | allowed list; an empty list allows none | an entry outside the list |
| `detectors` | required set | nothing: added to every profile |
| `[[locklog.bounds.pii_mask]]` | `sources` (globs), `field`, `label`, `mode`, `kind`, as a PII rule of locklog | nothing: applied before the project's rules, shown `(managed)` |

`[locklog.defaults]` takes the scalar profile keys, `auto` and `limits.*`,
not `sources`. `[locklog.profiles.<name>]` takes every profile key,
`sources` included, of locklog's
[usage](https://github.com/DavidGodefroid/locklog/blob/main/docs/usage.md#managed-configuration).

### `[lox]`

| Key | Type | Meaning |
|---|---|---|
| `auto_max` | table: action → `auto`, `ask` or `deny` | The loosest `lox run` auto rule per action: `connect`, `read`, `write`, `ddl`, `endpoint`, `policy`, `action`. `deny` refuses (`blocked by company policy: lox.auto_max.ddl = deny`); `ask` makes a human answer. Manual mode stays manual. |
| `production_auto_max` | same | The same ceiling for production tickets, with `auto_max`: the stricter wins. |
| `allow_no_upgrade` | bool, default `true` | `false` refuses `lox run --no-upgrade`: `--no-upgrade: blocked by company policy: lox.allow_no_upgrade = false`. |
| `image_min` | table: Lock → release tag `vX.Y.Z` | The oldest image `lox` may run per Lock (`locksql`, `lockmq`, `lockfile`, `lockhttp`, `lockssh`, `locklog`). An older image, or one whose signature names no release, is not started. |
| `egress` | list of `host:port` patterns (host a DNS name, `*.name` or `*`; port a number or `*`) | The endpoints a Lock may reach: an endpoint outside it is not started (`blocked by company policy: lox.egress does not allow <endpoint> (lock <name>)`). An empty list is refused: remove the key instead. lockhttp's own egress is not bounded by it. |

`lox` reads the host's file, shows it in the review (`managed: Example
Corp sha256:… signed`), applies `[family] vault`, runs each Lock's
`managed check` and mounts the file in the Locks' containers ([Locks in
containers](#locks-in-containers)). A file `lox` refuses stops `lox run`
before anything starts, with exit code 3.

### `[lea]`

lea ([lea#399](https://github.com/DavidGodefroid/lea/issues/399), in lea's
next release) reads the host's file in its launcher and its daemon, after
the user's `lea.conf`, and wins over it. A file lea refuses (ownership,
signature, an unknown `[lea]` key, a bad value) stops `lea` and its daemon
from starting, with the reason.

| Key | Type | Meaning |
|---|---|---|
| `approvals` | `"deck"` or `"pane"` | Who answers the agents' permission requests (`LEA_APPROVALS`), enforced. lea's approvals are never off: there is no `"required"`. |
| `autoupdate` | `true` only | Forces `LEA_AUTOUPDATE=1`. Every release lea installs is checked with cosign anyway (no way to turn that off). |
| `grant_ttl_max` | duration from `1m` to `30d` (`8h`, `90m`, `7d`) | The longest life of a grant. `lea allow --for` and `lea approve --expires` beyond it are refused; a lead's grant request is shortened to it; a grant recorded before ends once it is that old. An allowance that holds until revoked is refused too. |
| `standing_grants` | bool, default `true` | `false` refuses `lea allow` without `--for`; the allowances already recorded until revoked stop applying (`lea allow` shows them suspended by company policy). |
| `egress_allow` | list of domain names, each with its subdomains; `"default"` is lea's default list | The agents' web egress at most: lea-proxy gets the user's `LEA_EGRESS_ALLOW` within it, and the model API (anthropic.com, claude.ai, claude.com) always. `lea egress allow` refuses a domain outside it. With it, `LEA_LOCKHTTP=1` is refused unless the file has a `[lockhttp]` section for the gate. An empty list is refused: remove the key instead. |
| `claude_enforced` | table: Claude Code setting → value | Set in every agent's managed settings, over `lea config claude`, which refuses to change them: `defaultMode` (not `bypassPermissions`), `model`, `language`, `outputStyle`, `alwaysThinkingEnabled`, `disableBypassPermissionsMode = "disable"`. Any other key is refused. |

A user value beyond the file is ignored with a warning
(`warning: LEA_APPROVALS=pane is ignored: blocked by company policy:
lea.approvals = deck (...)`), or refused for the commands that would record
it: `lea allow`, `lea approve --expires`, `lea egress allow`, `lea config
claude`, and `lea config import`, refused as a whole with nothing written.
`lea doctor` prints `Managed by <organisation> (sha256:…)` and the active
rules, the deck's header names the organisation, and each allowance and
each use of one records the file's sha256. The daemon reads the file again
at every grant decision: a file that stops loading ends every grant until
it is fixed. The configuration keys apply at the next `lea`, and
`claude_enforced` to the lea containers started after the change.

## Example

The same file is [`examples/managed/managed.toml`](../examples/managed/managed.toml).
Every released tool of the table at the top of this page reads it
(`<tool> managed show` exits 0) and accepts the profiles within it.

```toml
# /etc/lockfamily/managed.toml
version = 1
organisation = "Example Corp"

[family]
require_signature = false
vault = { address = "https://vault.example.com", required = true }

[locksql.bounds]
tier = "write"                       # never ddl or admin
tls = "verify-full"
credentials = ["vault"]
hosts = ["*.db.example.internal"]
credentials_ttl = "8h"
write_functions = "allowlist"
auto = { ddl = "deny", unmask = "ask" }
detectors = ["email", "iban"]
limits.max_rows = 10000
limits.max_session = "8h"

[[locksql.bounds.pii_mask]]
column = "*.*.email"
mode = "email"

[locksql.defaults]
limits.statement_timeout = "30s"

[locksql.profiles.prod-erp]          # provided and locked
engine = "postgres"
host = "erp.db.example.internal"
database = "erp"
tls = "verify-full"
tier = "read"
production = true
credentials = "vault"
vault_path = "database/creds/erp-readonly"
credentials_ttl = "1h"
write_functions = "allowlist"
auto = { ddl = "deny", unmask = "ask" }  # within locksql.bounds.auto

[lockmq.bounds]
tier = "read"                        # never peek
tls = "verify-full"
credentials = ["vault"]
hosts = ["*.mq.example.internal"]
auto = { purge = "deny", delete = "deny", publish = "ask" }
limits.read_max = 100

[[lockmq.bounds.pii_mask]]
queue = ["*/*"]
body = "$.customer.email"

[lockssh.bounds]
hosts = ["*.example.internal"]
known_hosts = "/etc/ssh/ssh_known_hosts"
auth = ["key"]
exec = false
auto = { connect = "ask", run = "ask", exec = "deny", unmask = "deny" }
limits.max_session = "4h"

[lockfile.bounds]
source = ["s3", "sftp"]
hosts = ["*.example.internal", "s3.eu-west-1.amazonaws.com"]
max_object_bytes = "10MiB"
marketplaces = ["official"]

[lockhttp.bounds]
mode = "enforce"                     # no shadow mode
trusted = ["*.example.com"]
deny = ["pastebin.com"]

[[lockhttp.bounds.rules]]
id = "no-prod-writes"
host = "api.example.com"
methods = ["POST", "PUT", "PATCH", "DELETE"]
verdict = "ask"

[locklog.bounds]
kinds = ["file", "loki"]
unmask = "never"
detectors = ["email"]

[lox]
auto_max = { ddl = "deny", write = "ask", policy = "ask" }
production_auto_max = { read = "ask" }
allow_no_upgrade = false
image_min = { locksql = "v0.18.0", lockmq = "v0.9.0", lockfile = "v0.9.0", lockhttp = "v0.9.0", lockssh = "v0.2.0", locklog = "v0.3.0" }

[lea]                                # applied from lea's next release
approvals = "deck"
autoupdate = true
grant_ttl_max = "7d"
standing_grants = false
egress_allow = ["default", "example.com"]

[lea.claude_enforced]
defaultMode = "default"
```

## Commands

Every Lock has two read-only commands; neither connects nor asks for a
credential:

| Command | What it prints | Exit code |
|---|---|---|
| `<tool> managed show` | The file as the tool reads it: the `Managed by …` line, `path:`, `organisation:`, `fingerprint:`, `signed: yes` or `no`, then its bounds, defaults and managed profiles. | 0; 3 when the file is refused, with the reason on stderr. |
| `<tool> managed check [--profile NAME]` | Checks the configured profiles (or one) against the file, as the console does at start: one `blocked by company policy: …` line per violation, else a line naming the profiles within it (`ok: 2 profiles within the company policy (prod-erp, uat)`). | 0 within; 3 beyond, or when the file is refused. |
| `lox managed show` | The file as `lox` applies it: the same header, its `[lox]` rules, the `[family] vault` line and the sections it holds. | 0; 3 when the file is refused. |
| `lox doctor`, `<tool> doctor` | A `managed` line: `Managed by …`, `no managed configuration`, or `FAIL managed: <reason> (lox run refuses to start: ask your administrator to fix it)`. | |

`managed check` takes `--project DIR` in lockmq, lockssh and locklog, and
`--config FILE` in lockhttp; lockfile and lockhttp exit 1 when the tool's
own config file is missing. lockhttp's `managed show` starts at `path:`.
Without a file, each prints `no managed configuration` and exits 0. `lox
run` runs each Lock's `managed check` before it starts it; its output and
exit codes are a contract. `lox managed show` on the example:

```
Managed by Example Corp (sha256:a7948fe2424a)
path: /etc/lockfamily/managed.toml
organisation: Example Corp
fingerprint: sha256:a7948fe2424ab232b7fa7505701e64f01a2e3bc9e707c0b1f1ce1279224aacd1
signed: no
lox:
  auto_max.ddl = deny
  auto_max.policy = ask
  auto_max.write = ask
  production_auto_max.read = ask
  image_min.lockfile = v0.9.0
  image_min.lockhttp = v0.9.0
  image_min.locklog = v0.3.0
  image_min.lockmq = v0.9.0
  image_min.locksql = v0.18.0
  image_min.lockssh = v0.2.0
  allow_no_upgrade = false
vault from the managed configuration ([family] vault): https://vault.example.com, required
sections: lockfile, lockhttp, locklog, lockmq, locksql, lockssh
```

## Signing

A signature proves the file is the one the company published, not one an
administrator account wrote by hand. v1 supports **keyless** cosign only:
the file is signed by a CI workflow whose identity is in the certificate.
Signing with a key pair waits for
[lockkit#15](https://github.com/DavidGodefroid/lockkit/issues/15) and is not
supported.

1. Keep `managed.toml` in a repository of the company, and sign it with the
   workflow [`examples/managed/sign.yml`](../examples/managed/sign.yml)
   (`.github/workflows/sign.yml` there). Its core:

   ```yaml
   permissions:
     contents: write
     id-token: write   # the OIDC token cosign signs with
   steps:
     - uses: sigstore/cosign-installer@6f9f17788090df1f26f669e9d70d6ae9567deba6 # v4.1.2
     - run: cosign sign-blob --yes --bundle managed.toml.sigstore.json managed.toml
   ```

2. Write `signer.toml`, the identity the tools accept. Both keys are
   required: `certificate_identity_regexp` must start with `^https://` and
   `oidc_issuer` must be an `https://` URL
   ([`examples/managed/signer.toml`](../examples/managed/signer.toml)):

   ```
   certificate_identity_regexp = "^https://github.com/<org>/<repo>/.github/workflows/sign.yml@refs/heads/main$"
   oidc_issuer = "https://token.actions.githubusercontent.com"
   ```

3. Deploy the three files together, root-owned, in the managed directory
   (every [recipe](#deploying) has a switch for it), and install `cosign`
   on the hosts (`brew install cosign`, or the
   [release](https://github.com/sigstore/cosign/releases) the family's
   installer pins: [docs/install.md](install.md)).
4. Set `[family] require_signature = true` once every host has the bundle:
   from then on, a host without it refuses to start.

Check a bundle before deploying it, with the same identity:

```sh
cosign verify-blob --bundle managed.toml.sigstore.json \
  --certificate-identity-regexp '^https://github.com/<org>/<repo>/.github/workflows/sign.yml@refs/heads/main$' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  managed.toml
```

`<tool> managed show` and `lox managed show` then print `signed: yes` and
`Managed by <organisation> (sha256:…, signed)`. Any change to one byte of
`managed.toml`, of the bundle or of `signer.toml` without signing again is a
refusal: `the signature does not verify`. The tools re-check the signature
only when one of the three files changes.

## Deploying

Each recipe installs the directory `0755` and the files `0644`, owned by
`root:root` (macOS `root:wheel`). It installs `managed.toml`, and
`signer.toml` with the bundle when you sign. No restart is needed: a
running console reads the new file at its next policy check, and `lox run`
applies a change of the file alone without an `Apply?` question.

### Ansible

[`examples/managed/ansible/tasks.yml`](../examples/managed/ansible/tasks.yml)
creates the directory and copies the files with `ansible.builtin.copy`
(`owner`, `group`, `mode`);
[`playbook.yml`](../examples/managed/ansible/playbook.yml) picks the paths
and group per OS (Linux and macOS):

```yaml
- name: Lock Family managed files
  ansible.builtin.copy:
    src: "{{ lockfamily_files }}/{{ item }}"
    dest: "{{ lockfamily_managed_dir }}/{{ item }}"
    owner: root
    group: "{{ lockfamily_root_group }}"
    mode: "0644"
  loop: "{{ ['managed.toml'] + (['signer.toml', 'managed.toml.sigstore.json'] if lockfamily_signed | bool else []) }}"
```

```sh
ansible-playbook -i inventory examples/managed/ansible/playbook.yml -e lockfamily_signed=true
```

### Debian and rpm packages

[`examples/managed/nfpm.yaml`](../examples/managed/nfpm.yaml) builds a deb
and an rpm with [nfpm](https://nfpm.goreleaser.com/): `contents:` entries
with `file_info` modes and owners, the signature entries ready to
uncomment. Bump `version` with every change of the policy and publish the
package in the repository your hosts already update from:

```sh
cd examples/managed
nfpm package -p deb -f nfpm.yaml    # example-corp-lockfamily-managed_1.0.0-1_all.deb
nfpm package -p rpm -f nfpm.yaml
sudo apt install ./example-corp-lockfamily-managed_1.0.0-1_all.deb
```

The files are not marked as configuration files: an upgrade of the package
replaces them, even if someone changed them by hand.

### macOS

[`examples/managed/macos/build.sh`](../examples/managed/macos/build.sh)
builds a `.pkg` with `pkgbuild`: its payload is
`/Library/Application Support/lockfamily/`, and its
[`postinstall`](../examples/managed/macos/scripts/postinstall) script sets
`root:wheel`, `0755` and `0644`:

```sh
cd examples/managed
sh macos/build.sh 1.0.0           # example-corp-lockfamily-managed-1.0.0.pkg
sudo installer -pkg example-corp-lockfamily-managed-1.0.0.pkg -target /
```

To deploy it through an MDM, sign the `.pkg` with your Developer ID
Installer certificate (`productsign`) and upload it as a package:

- **Jamf Pro**: Settings → Computer management → Packages, then a policy
  that installs it, scoped to the fleet, triggered at check-in.
- **Microsoft Intune**: Apps → macOS → Add → macOS app (PKG), assigned as
  required to the device groups.

## Verifying a deployment

On a host, after the deployment:

1. `ls -ld <directory> <directory>/*`: `root root` (`root wheel` on macOS),
   `drwxr-xr-x` and `-rw-r--r--`.
2. `lox managed show`: `Managed by <organisation> (sha256:…)`, `signed:
   yes` when you sign, and the rules you wrote.
3. `<tool> managed check` in a project of each Lock: `… within the company
   policy`, or the lines to fix in the user's or project's profiles.
4. `lox doctor`: `managed: Managed by …`.

## Troubleshooting

Every tool reports the same reason, after `managed: <path>:` (`lox run:
…`, `<tool> managed show: …`, `blocked by company policy: …` in `managed
check`); a refused file always exits 3.

| Message | Fix |
|---|---|
| `must be writable by root only (mode 0666)` | `chmod 0644` the file (`0755` its directory). |
| `must be owned by root (it is owned by uid 1000)` | `chown root:root` (`root:wheel`) the file and its directory. |
| `is not a regular file` | Copy the file in place of the symbolic link. |
| `invalid TOML at line N` | Fix the syntax; `python3 -c 'import tomllib,sys; tomllib.load(open(sys.argv[1],"rb"))' managed.toml` finds it. |
| `version = 1 is required`, `version 2 is not supported (this build reads version 1)` | Set `version = 1`. |
| `unknown key "lockvpn"`, `[lox]: unknown key "egress_allow"` | A section or key of no tool, or a typo: only the tool whose section it is refuses. |
| `key "token" looks like a secret; the managed file holds no secrets` | Remove it: the file is readable by every user. |
| `[locksql.profiles.prod-erp]: the managed profile is beyond the managed bounds: locksql.bounds.auto.ddl = deny (profile prod-erp: auto.ddl = ask)` | A managed profile must sit within the bounds, built-in defaults included: set the field in the profile (`auto = { ddl = "deny" }`). |
| `is signed but …/signer.toml, the company identity to check it against, is missing` | Deploy `signer.toml` with the bundle. |
| `certificate_identity_regexp must be an anchored ^https:// regexp and oidc_issuer an https:// URL` | Fix `signer.toml`. |
| `the signature does not verify: cosign is not installed` | Install `cosign` on the host's `PATH`. |
| `the signature does not verify: …` | The file, the bundle or `signer.toml` changed since signing, or the identity does not match: sign again, or fix `signer.toml`. |
| `[family] require_signature is set but managed.toml.sigstore.json is missing` | Deploy the bundle. |
| `is signed, but this lox cannot vouch for its signature inside the locks' containers (…): upgrade lox` | Upgrade `lox` to v0.11.0 or later. |
| `<tool> vX.Y.Z predates managed support: upgrade it or set [lox] image_min` | Upgrade that Lock (`lox run` updates it unless `--no-upgrade`). |
| `blocked by company policy: lox.image_min.locksql = v0.18.0 (the image is locksql v0.17.2)` | Run `lox run` without `--no-upgrade`, or pin a newer release. |
| `blocked by company policy: <key> …` in `managed check` | The user's or project's profile goes beyond the bounds: tighten it (see [Violations](#violations)). |
| `profile "<name>" is provided by the company's managed configuration and cannot be redefined in the project config: rename yours` | Rename the user's or project's profile. |
| `managed: … changed while lox read it: lox run again` | The file was replaced during `lox run`'s read: run it again. |
