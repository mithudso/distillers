# Contributing

Start with [development](docs/DEVELOPMENT.md), [testing](docs/TESTING.md), and
[CLAUDE.md](CLAUDE.md). Use Python 3.11+ and a feature branch. Keep fixes grounded
in observable behavior; preserve mirror banners, source provenance, stdlib core
operation, and the optional embedding fallback.

Add regression assertions for changed risky paths, run `make check`, and run
`mirror --in` on a known docset. Generate current metadata with `make docs`.
Record the request and outcome in `prompts.md` and `memory.md`; bump the package
patch version for the delivered logical change. Do not alter frozen one-off
scripts or commit private corpora, credentials, caches, or generated distillations.

Open a PR describing the trigger, resulting behavior, tests, risks, and rollback.
Wait for checks on the final pushed commit before merging. See the
[release runbook](docs/runbooks/release-and-rollback.md). Follow the
[code of conduct](CODE_OF_CONDUCT.md); report sensitive issues using
[the security policy](.github/SECURITY.md).
