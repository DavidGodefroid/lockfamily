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
installed. The signatures are checked with the cosign on your PATH when it
is v3 or later. Otherwise the installer downloads the cosign release pinned
in `install.sh` and checks it against the sha256 pinned there. A cosign
older than v3 on your PATH is used for nothing and left alone; only when no
cosign is on your PATH at all is the downloaded one installed as
`~/.local/bin/cosign`, once everything else is installed.

## Verifying the installer

`install.sh` verifies what it installs; the script itself is signed too.
The Pages workflow of this repository (`.github/workflows/pages.yml`) signs
it keyless with cosign on every deployment, in a job that runs nothing but
the checkout and cosign, and serves the bundle beside it,
at <https://lockfamily.dev/install.sh.sigstore.json>. To check the script
before you run it, with cosign v3 or later:

```sh
curl -fsSLO https://lockfamily.dev/install.sh
curl -fsSLO https://lockfamily.dev/install.sh.sigstore.json
cosign verify-blob --bundle install.sh.sigstore.json \
  --certificate-identity https://github.com/DavidGodefroid/lockfamily/.github/workflows/pages.yml@refs/heads/main \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  install.sh && sh install.sh
```

What the check proves: the script you downloaded is one that workflow
published from the `main` branch of this repository. Its limits:

- no freshness: an older `install.sh` with its old bundle still verifies
  under the same identity, so the check does not prove that the script is
  the current one;
- the command above and the script come from the same GitHub account, so
  the check does not protect against that account being taken over;
- it says nothing about where your agent runs: the guarantees of the Locks
  hold against a compromised or prompt-injected agent only when the agent
  itself runs confined, as in lea
  ([security model](https://lockfamily.dev/docs/security/));
- `curl … | sh` without this check trusts the HTTPS connection to
  lockfamily.dev alone.

Without cosign at hand, Homebrew is the other verified route:
`brew install davidgodefroid/tap/lockfamily` checks every download against
its formula's sha256. The workflow verifies the bundle before it deploys,
then fetches the published script and bundle and verifies them again.

## lox alone

`--version vX.Y.Z` installs only `lox`, from that lockhub
release, as before (a downloaded cosign is then used for the check only).
Without cosign, add `--sha256 <hash>` with a hash you trust: the archive is
checked against that hash only, and the cosign check is skipped. It is
still downloaded, from GitHub's releases or the [mirror](#mirrors) you set:

```sh
curl -fsSL https://lockfamily.dev/install.sh | sh -s -- --version vX.Y.Z
```

## Mirrors

Two variables point the installer at copies you host (an `https://` URL, or
an absolute local directory):

| Variable | What it holds |
|---|---|
| `LOCK_RELEASE_BASE` | the releases, as `<repository>/vX.Y.Z/` folders (with `--version`: lockhub's `vX.Y.Z/` folders) |
| `LOCK_TAP_BASE` | the tap, as `Formula/<tool>.rb` |

The signatures are checked against the same release-workflow identities as
from GitHub, so a mirror must hold the releases' own `checksums.txt` and
signature bundles. Without GitHub, put a cosign v3 on your PATH (the
fallback cosign is downloaded from GitHub), or use `--version` with
`--sha256`.

The per-tool install scripts stay, except lockhttp's, which is removed
(lockhttp#40).

## Tests

Against fake releases of every tool, a fake tap, a stub cosign and a fake cosign download, with no network: `sh tests/install_test.sh`
(`COSIGN_REAL=$(command -v cosign)` adds a real cosign check).

