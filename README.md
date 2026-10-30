# lockfamily.dev

The one-page site of the lock family: [locksql](https://github.com/DavidGodefroid/locksql),
[lockmq](https://github.com/DavidGodefroid/lockmq),
[lockfile](https://github.com/DavidGodefroid/lockfile),
[lockhttp](https://github.com/DavidGodefroid/lockhttp),
[lea](https://github.com/DavidGodefroid/lea), and the approval hub
[lockhub](https://github.com/DavidGodefroid/lockhub) with its `lock` CLI.

Static HTML, CSS and vanilla JavaScript: no build step, no tracking. Served by GitHub Pages
from the repository root (`CNAME`: `lockfamily.dev`).

Preview locally:

```sh
python3 -m http.server -d . 8080
```

## The approval hub and the `lock` CLI

[lockhub](https://github.com/DavidGodefroid/lockhub) lets every lock of a
workspace hand its approvals to one hub: the lock sends a signed ticket with
the masked screen of the request, the human answers from a facade, the hub
signs the decision, bound to the exact plan, and the lock runs only on it. The
hub never runs a request, never sees its results, never sees values in clear.

The `lock` CLI (installed by `install.sh`, below):

| Command | What it does |
|---|---|
| `lock add TYPE INSTANCE --image REF [--hub-image REF]` | declare a lock (locksql, lockmq, lockfile, lockhttp), pinned to a signed image; the first one also pins the hub's image |
| `lock add slack …`, `lock add telegram …` | enable a chat facade; its tokens are asked at the terminal and kept out of the projects |
| `lock import [SUB…]` | merge sub-projects' `lockfamily.yaml`, keeping the strictest routing |
| `lock up` | review the configuration (all of it the first time, the change afterwards), then start the hub and the locks |
| `lock approve` | answer tickets in this terminal |
| `lock doctor` | check the hub, the locks, keys, the facade socket and the network; changes nothing |
| `lock audit verify --data DIR --hub-key-file FILE` | check the hub's audit chain and every decision's signature |

`lock add` and `lock import` only edit `lockfamily.yaml`: the next `lock up`
reviews the change with you.

Facades: the terminal (`lock approve`), the [lea](https://github.com/DavidGodefroid/lea)
deck, Slack and Telegram. Chat facades show masked screens and answer only
non-production reads and writes: production tickets, policy loosening and
unlocks are answered in the terminal or the deck. A workspace can narrow this
routing, never widen it. Locks need their hub-mode releases.

## install.sh

`install.sh`, served at <https://lockfamily.dev/install.sh>, installs the `lock`
CLI of the approval hub ([lockhub](https://github.com/DavidGodefroid/lockhub))
and nothing else: only `~/.local/bin/lock`, no sudo, no image pulled.

```sh
curl -fsSL https://lockfamily.dev/install.sh | sh
# or a given release:
curl -fsSL https://lockfamily.dev/install.sh | sh -s -- --version vX.Y.Z
```

It needs cosign: the keyless signature of the release's `checksums.txt` must
come from the lockhub release workflow run for that tag, and the archive must
match it. Without cosign it refuses, unless you pass `--version` and
`--sha256 <hash>` with a hash you trust. The per-tool install scripts stay.

Tests (fake release, stub cosign, no network): `sh tests/install_test.sh`
(`COSIGN_REAL=$(command -v cosign)` adds a real cosign check).

Logos and the lea demo come from each project's own repository.

Apache-2.0, see [LICENSE](LICENSE).
