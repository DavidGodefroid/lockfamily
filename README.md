# lockfamily.dev

The one-page site of the lock family: [locksql](https://github.com/DavidGodefroid/locksql),
[lockmq](https://github.com/DavidGodefroid/lockmq),
[lockfile](https://github.com/DavidGodefroid/lockfile),
[lockhttp](https://github.com/DavidGodefroid/lockhttp) and
[lea](https://github.com/DavidGodefroid/lea).

Static HTML, CSS and vanilla JavaScript: no build step, no tracking. Served by GitHub Pages
from the repository root (`CNAME`: `lockfamily.dev`).

Preview locally:

```sh
python3 -m http.server -d . 8080
```

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
