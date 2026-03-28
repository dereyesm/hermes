# Contributing to HERMES

HERMES is a community-driven protocol. Contributions are welcome from anyone who believes AI agents should communicate through open, transparent, file-based standards — no proprietary platforms, no vendor lock-in.

## Ways to Contribute

### 1. Propose a New Standard (ARC/ATR/AES)

The standards process is modeled after the IETF RFC system:

1. **Open an issue** using the [ARC Proposal template](.github/ISSUE_TEMPLATE/arc-proposal.md)
2. **Community discussion** happens in the issue thread
3. **Draft PR** — once there's rough consensus, submit a PR with the spec in `spec/`
4. **Review cycle** — the maintainer reviews all PRs; additional reviewers welcome
5. **Merge** — the standard moves from DRAFT to IMPLEMENTED when a reference implementation exists

**Numbering convention**:
- `ARC-NNNN` — IETF lineage (Agent Request for Comments)
- `ATR-X.NNN` — ITU-T lineage (Agent Telecom Recommendation)
- `AES-NNN.NN` — IEEE lineage (Agent Engineering Standard)

Maintainers assign the final number. Use `ARC-NNNN` as placeholder in your proposal.

### 2. Improve the Reference Implementation

The Python reference implementation lives in `reference/python/`. To contribute:

```bash
cd reference/python
pip install -e ".[dev]"
python -m pytest tests/
```

Guidelines:
- Keep it minimal — the reference implementation demonstrates the spec, not a production framework
- Every public function needs a docstring
- Tests are required for new functionality
- External dependencies: `cryptography` (Ed25519/X25519), `tomli-w` (TOML writing), `msgpack` (compact encoding). Keep the list minimal.

### 3. Add a New Language Implementation

Want HERMES in Rust, Go, TypeScript, or another language? Create a directory under `reference/`:

```
reference/
├── python/     # existing
├── rust/       # your contribution
└── typescript/ # your contribution
```

Each implementation should pass the same logical test suite and validate against `examples/bus-sample.jsonl`.

### 4. Improve Documentation

- Fix typos, clarify language, add diagrams
- Translate docs (create `docs/lang/` directories)
- Add real-world deployment examples to `examples/`

### 5. Report Issues

Found a bug in the spec? An ambiguity? A security concern? Open an issue. No issue is too small.

## Code of Conduct

This project follows one rule: **build for the collective, not for control.**

- Be respectful and constructive
- Credit prior art (IETF, ITU-T, IEEE — we stand on their shoulders)
- No proprietary extensions that break interoperability
- No surveillance, no tracking, no dark patterns

## Development Setup

```bash
git clone https://github.com/dereyesm/hermes.git
cd hermes
cd reference/python
pip install -e ".[dev]"
python -m pytest tests/
```

## Pull Request Process

1. Fork the repo and create a feature branch
2. Make your changes
3. Ensure tests pass
4. Update relevant docs if the spec changes
5. Submit a PR with a clear description

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
