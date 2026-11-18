# Contributing to the Lock Family

Issues and pull requests are welcome, in English, on the repository they
concern.

## Where things go

- **A question, an idea, "how do I…":**
  [Discussions](https://github.com/DavidGodefroid/lockfamily/discussions),
  for the whole family.
- **A bug or a change:** an issue or a pull request on the repository that
  holds the code or the page.
- **A vulnerability:** never a public issue. See [Security](#security).
- **A first task:** the issues labelled
  [good first issue](https://github.com/search?q=owner%3ADavidGodefroid+label%3A%22good+first+issue%22+state%3Aopen&type=issues)
  across the family.

| The change is about | Repository |
|---|---|
| This README, the home page of lockfamily.dev, `install.sh`, the docs generator (`docs-site/`), the `lox` and managed-configuration references (`docs/`) | [lockfamily](https://github.com/DavidGodefroid/lockfamily) (here) |
| A page of lockfamily.dev/docs about one tool | That tool's repository: the page is built from its README or its `docs/` (`docs-site/nav.toml` says which file) |
| `lox` (`lox add`, `lox run`, `lox audit`…), the hub, approvals, facades | [lockhub](https://github.com/DavidGodefroid/lockhub) |
| SQL databases | [locksql](https://github.com/DavidGodefroid/locksql) |
| RabbitMQ | [lockmq](https://github.com/DavidGodefroid/lockmq) |
| Files (S3, SFTP, disk) | [lockfile](https://github.com/DavidGodefroid/lockfile) |
| Outbound HTTP(S) | [lockhttp](https://github.com/DavidGodefroid/lockhttp) |
| Logs | [locklog](https://github.com/DavidGodefroid/locklog) |
| Commands over SSH | [lockssh](https://github.com/DavidGodefroid/lockssh) |
| What every Lock shares: the console, policies, masking, signed tickets, audit, MCP wiring | [lockkit](https://github.com/DavidGodefroid/lockkit) |
| Running agents in containers, the deck | [lea](https://github.com/DavidGodefroid/lea) |
| The Homebrew formulas | [homebrew-tap](https://github.com/DavidGodefroid/homebrew-tap) |

Not sure which one? Open the issue here.

## Working on this repository

There is nothing to build for the home page: it is static HTML, CSS and
vanilla JavaScript. Preview it, or build the whole site with the docs:

```sh
python3 -m http.server -d . 8080
python3 -m venv /tmp/docs && /tmp/docs/bin/pip install --require-hashes -r docs-site/requirements.txt
/tmp/docs/bin/python docs-site/build.py --out _site && python3 -m http.server -d _site 8080
```

Run the tests of what you touched before you open a pull request. All but
the last run with no network:

| You changed | Run |
|---|---|
| `install.sh` | `sh tests/install_test.sh` (`COSIGN_REAL=$(command -v cosign)` adds a real cosign check) |
| `README.md`, `docs/` | `sh tests/readme_test.sh` |
| `index.html`, `assets/` | `sh tests/site_test.sh` (contrast, fonts, logos, the page at 360, 768 and 1280 px in a headless Chrome) |
| `tools/flow_svg.py`, `assets/flow-*.svg` | `sh tests/flow_svg_test.sh` |
| `docs-site/` | `sh tests/docs_test.sh` (needs network and markdown-it-py) |

CI runs them all on every pull request, with `shellcheck -s sh` on the
shell scripts: `install.sh` and the tests are POSIX `sh`, and run under
dash and busybox.

Generated files are not edited by hand: the logos come from
`python3 tools/logo_svg.py`, the animated flow from
`python3 tools/flow_svg.py`.

## Pull requests

- English, in the code, the commits and the discussion.
- One subject per pull request, with the issue it closes (`Closes #N`).
- Say how you verified it; for a visual change, add before and after
  screenshots.
- Documentation states what the tools do today. Do not soften or drop a
  stated limit of the security model, and check every claim against the
  code or the existing docs.

## Security

Please do not open a public issue for a vulnerability: follow the affected
repository's `SECURITY.md`, or contact the maintainer privately through
GitHub.

## License

Apache-2.0, see [LICENSE](LICENSE). Contributions are under the same
license (its section 5).
