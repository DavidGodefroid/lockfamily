# lockfamily.dev

The one-page site of the lock family: [locksql](https://github.com/DavidGodefroid/locksql),
[lockmq](https://github.com/DavidGodefroid/lockmq),
[lockfile](https://github.com/DavidGodefroid/lockfile),
[lockhttp](https://github.com/DavidGodefroid/lockhttp),
[lea](https://github.com/DavidGodefroid/lea), and the approval hub
[lockhub](https://github.com/DavidGodefroid/lockhub) with its `lox` CLI.

Static HTML, CSS and vanilla JavaScript: no build step, no tracking. Served by GitHub Pages
from the repository root (`CNAME`: `lockfamily.dev`).

Preview locally:

```sh
python3 -m http.server -d . 8080
```

## The approval hub and the `lox` CLI

[lockhub](https://github.com/DavidGodefroid/lockhub) (v0.2, pre-release) lets
every lock of a workspace hand its approvals to one hub. The lock sends a
signed ticket with the masked screen of the request, the human answers from a
facade, and the hub signs the decision, bound to the exact plan. The lock runs
only on that signed decision. The hub never runs a request, never sees its
results, and never sees values in clear.

### Quick start, with locksql

```sh
curl -fsSL https://lockfamily.dev/install.sh | sh   # lox, lea, the launchers
cd ~/projects                  # the workspace: lea's projects directory
lox add locksql crm            # latest signed locksql, by digest; pins the hub's image too
mkdir -p .locksql              # the lock's profile, in the workspace
cat > .locksql/config.toml <<'TOML'
[profiles.crm]
engine = "postgres"
host = "host.docker.internal"
port = 5432
user = "ro"
database = "app"
tls = "disable"                # host.docker.internal is not loopback: TLS defaults to verify-full
TOML
chmod -R go-w .locksql        # lox up refuses a profile others can write (umask 002)
lox up                         # review everything, then start the hub and the lock
lox attach crm                 # the console's start-up questions; detach: Ctrl-P Ctrl-Q
lox approve                    # answer tickets (or from the lea deck)
```

Docker and cosign are required: `lox add` and `lox up` check every image's
signature against its release workflow. On Linux the database must listen on
the Docker bridge, not only on 127.0.0.1 (`host.docker.internal` is the host's
gateway). Agents that lea starts after `lox up` (with `LEA_LOCKSQL=1`, the
default) get the lock's socket.

### Commands (lox)

| Command | What it does |
|---|---|
| `lox add TYPE INSTANCE [--version vX.Y.Z \| --image REF] [--profile P] [--hub-image REF]` | declare a lock (locksql, lockmq, lockfile, lockhttp), pinned by digest to its latest (or the given) signed release; the first one also pins the hub's latest release |
| `lox add slack --team T… --channel C… --user U…` | enable the Slack facade; its tokens are asked at the terminal and kept with the hub's data, never in the workspace |
| `lox add telegram --chat ID --from ID` | enable the Telegram facade (bot token asked at the terminal) |
| `lox import [SUB…]` | merge sub-projects' `lockfamily.yaml`, keeping the strictest routing |
| `lox up [--dry-run] [--pin sha256:DIGEST] [--rotate hub\|INSTANCE\|all]` | review the configuration (all of it the first time, the change afterwards), then start the hub and the locks; `--pin` runs the hub on a previous image (by digest), `--rotate` (repeatable) replaces the hub's or a lock's key |
| `lox attach INSTANCE` | answer a lock console's start-up questions (policy, credentials) |
| `lox approve [--once]` | answer tickets in this terminal: `y`, `n reason`, `s`, `q`; `o` (or Ctrl-O then Enter, where the terminal passes it: not on macOS) shows clear values; `r` approves an expired ticket again |
| `lox mobile pair --name NAME`, `lox mobile list`, `lox mobile revoke NAME` | pair a phone (one-time code, confirmed at the terminal), list or revoke phones; `lox up` then pins or unpins them at the locks |
| `lox doctor` | check the hub, the locks, keys, the facade socket and the network; changes nothing |
| `lox audit verify --data DIR --hub-key-file FILE [--lock INSTANCE=PATH] [--anchors FILE]` | check the hub's audit chain and every decision's signature, and optionally a lock's own log against them |

The workspace commands (`add`, `import`, `up`, `attach`, `doctor`, `mobile`)
take `--file` to name another `lockfamily.yaml`. `lox add` and `lox import`
only edit it: the next `lox up` reviews the change with you.

### Facades and routing

Facades: the terminal (`lox approve`), the
[lea](https://github.com/DavidGodefroid/lea) deck, Slack, Telegram, and a
paired phone (an installable web app the hub serves; optional Web Push with no
payload). The hub routes each risk class:

| Risk class | Terminal, deck | Phone | Slack, Telegram |
|---|---|---|---|
| read, read-pii, write | yes | yes | yes, never a production ticket |
| prod-write, policy-loosen | yes | yes | no |
| unlock | yes | no | no |
| clear values | on demand, `o` (or Ctrl-O) (`reveal: true`) | sealed to it (`seal_clear`) | never |

A chat facade never answers a production ticket, whatever its risk class. A
workspace's `hub.routing` can narrow this per instance, never widen it.

- **Reveal.** With `reveal: true` on a lock, the terminal and the deck can ask
  for a ticket's clear values: the lock seals them to that facade's key, which
  it pins, and the hub relays ciphertext.
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
  facades: [tty, deck, mobile, slack]   # default: tty, deck
  routing:
    crm: [tty, deck, mobile]            # narrows an instance, never widens
  slack: {team: T0123, channel: C0123, users: [U0123]}
  mobile:
    origin: https://hub.example.ts.net
    seal_clear: true
    require_device: [prod-write]
    push: true
locks:
  crm:
    type: locksql
    image: ghcr.io/davidgodefroid/locksql@sha256:…
    devices: true
    reveal: true
```

It lives in the workspace's `.lockfamily/`, which lea mounts read-only in its
agents. A `lockfamily.yaml` at the workspace's root (the older layout) is
still read, with a warning, while `.lockfamily/` does not exist, and copied
there by the first confirmed `lox up`; once `.lockfamily/` exists, a root
file is never read.
A lock's target, production flag and credentials stay in its own profile
(`.locksql/`, `.lockmq/`, …), which `lox up` reviews and copies.
`lox up` writes `.lockfamily/up.json` for lea and keeps the hub's data, keys
and audit log under `$XDG_STATE_HOME/lockfamily/` (default
`~/.local/state/lockfamily/`).

### lea

lea follows the hub by default (`LEA_HUB=1`, from lea v0.3.0). An agent whose
Lock call waits for a decision is suspended until the decision comes, and
lea's deck shows and answers the hub's tickets. lea gives its agents the
locks' sockets named in `up.json`, never the hub. `LEA_HUB=0` switches it
off. The contract between the two is lockhub's
[docs/lox-up.md](https://github.com/DavidGodefroid/lockhub/blob/main/docs/lox-up.md).
Locks need their hub-mode releases; each lock's docs list the lockhub
versions it supports.

## install.sh

`install.sh`, served at <https://lockfamily.dev/install.sh>, installs the Lock
Family: the same tools, at the same versions, as the Homebrew meta formula
(`brew install davidgodefroid/tap/lockfamily`), into `~/.local/bin`, without
sudo and without pulling any image (each tool pulls its images, by digest, on
first use).

```sh
curl -fsSL https://lockfamily.dev/install.sh | sh
lox init
```

| Tool | Installed as |
|---|---|
| `lox` ([lockhub](https://github.com/DavidGodefroid/lockhub)) | `~/.local/bin/lox` |
| [`lea`](https://github.com/DavidGodefroid/lea) | the release tree in `~/.local/share/lea-install/vX.Y.Z`, linked as `~/.local/bin/lea` (as lea's own installer; `lox init` runs the rest) |
| `locksql`, `lockmq`, `lockhttp`, `lockfile` (Linux only) | the launchers, `~/.local/bin/<tool>`, which run their release's images by digest; lockfile's seccomp profile in `~/.local/share/lockfile/` |
| `cosign` | `~/.local/bin/cosign`, only when no cosign is on your PATH (the meta formula installs it too; `lox init` and the launchers' `update` use it) |

`locklog` has no published release yet and is skipped. Docker is required:
Docker Engine (Linux) or Docker Desktop (macOS) must be installed and
running. Next step: `lox init`.

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
