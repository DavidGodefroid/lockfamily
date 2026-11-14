# install.sh

`install.sh`, served at <https://lockfamily.dev/install.sh>, installs the Lock
Family: the same tools, at the same versions, as the Homebrew meta formula
(`brew trust davidgodefroid/tap`, then `brew install davidgodefroid/tap/lockfamily`), into `~/.local/bin`, without
sudo and without pulling any image (each tool pulls its images, by digest, on
first use).

```sh
curl -fsSL https://lockfamily.dev/install.sh | sh
lea
lox add locksql
```

| Tool | Installed as |
|---|---|
| `lox` ([lockhub](https://github.com/DavidGodefroid/lockhub)) | `~/.local/bin/lox` |
| [`lea`](https://github.com/DavidGodefroid/lea) | the release tree in `~/.local/share/lea-install/vX.Y.Z`, linked as `~/.local/bin/lea` (as lea's own installer) |
| `locksql`, `lockmq`, `lockhttp`, `locklog`, `lockssh`, `lockfile` (Linux only) | the launchers, `~/.local/bin/<tool>`, which run their release's images by digest; lockfile's seccomp profile in `~/.local/share/lockfile/`. From lea v0.16.0, lea's `LEA_LOCKHTTP=1` uses this `lockhttp` launcher (lea looks in `/usr/local/bin`, then `~/.local/bin`, then brew's `bin`); because it is user-writable, lea runs its pinned image as the gate only if the digest matches the pin in lea's `config/locks.lock` or `cosign verify` proves lockhttp's release signed it, so keep `cosign` installed. lockhttp's own `scripts/install.sh` is removed (lockhttp#40): this installer or brew is the way to install the `lockhttp` launcher, and lockhttp needs lea v0.16.0 or later |
| `cosign` | `~/.local/bin/cosign`, only when no cosign is on your PATH (the meta formula installs it too; `lox init` and the launchers' `update` use it) |

locklog's local log sources are Linux only; on macOS it reads the remote sources (Loki, Elasticsearch/OpenSearch). Docker is required:
Docker Engine (Linux) or Docker Desktop (macOS) must be installed and
running. Next step: `lox add <lock>` in your project, then `lox run` in a terminal of its own, outside the agent.

The installer itself never uses sudo. On Linux, lea does, once, in `lea init`
(the first `lea` runs it), and again only when what it installs changed: its
AppArmor profile where Docker uses AppArmor, and its egress log (an nftables
table `bridge lea_egress` in `/etc/lea/egress-log.nft`, loaded by
`lea-egress-log.service`) where Docker runs rootful and `nft` and systemd are
installed. When sudo would prompt, the first `lea` stops for AppArmor, or skips
the egress log, and says to run `lea init`. See lea's
[README](https://github.com/DavidGodefroid/lea#requirements).

## Versions

They come from the tap,
[DavidGodefroid/homebrew-tap](https://github.com/DavidGodefroid/homebrew-tap),
its single source of truth, which each project's release workflow bumps on
its tag: the tools that `Formula/lockfamily.rb` depends on, and in each
`Formula/<tool>.rb` the release URL for your system, its sha256 and the image
digests. The formulas are read as text, never run, and every value must match
a strict pattern.

## Verification

The tap only says which release. For every tool, the
keyless signature of the release's `checksums.txt` must come from that
project's release workflow run for that very tag, the archive must match
`checksums.txt` and the formula, and a launcher's image digests must be the
ones cosign verifies for that tag. Everything is verified before anything is
installed. The signatures are checked with the cosign on your PATH; without
one, it downloads cosign v3.0.6, checks it against the sha256 pinned in
`install.sh`, and, once everything else is installed, installs it as
`~/.local/bin/cosign`.

## lox alone

`--version vX.Y.Z` installs only `lox`, from that lockhub
release, as before (a downloaded cosign is then used for the check only);
offline, add `--sha256 <hash>` with a hash you trust:

```sh
curl -fsSL https://lockfamily.dev/install.sh | sh -s -- --version vX.Y.Z
```

The per-tool install scripts stay.

## Tests

Against fake releases of every tool, a fake tap, a stub cosign and a fake cosign download, with no network: `sh tests/install_test.sh`
(`COSIGN_REAL=$(command -v cosign)` adds a real cosign check).

