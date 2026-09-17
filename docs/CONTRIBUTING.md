# Contributing to aweswitch

`aweswitch` is intentionally small: a local agent profile launcher with a readable JSON config and a thin CLI.

The project should stay focused on that job. Prefer changes that make profile switching clearer, safer, or easier to maintain. Avoid turning it into a general agent manager or a broad configuration platform.

## Development Setup

Clone the repository and run the tests:

```bash
git clone https://github.com/wehuman01/aweswitch.git
cd aweswitch
python3 -m pip install -e .
python3 tests/test_aweswitch.py
python3 -m py_compile src/aweswitch/cli.py tests/test_aweswitch.py
```

For local CLI testing:

```bash
python3 -m pip install -e .
aweswitch --help
```

## Branches

The repository uses two long-lived branches:

- `main` is the stable line.
- `dev` is the integration branch for day-to-day development.

Do feature work on `dev` unless a maintainer says otherwise.

## Engineering Taste

Prefer solutions that are simple, clear, decoupled, honest, focused, and durable.

- Simple: make the smallest change that solves the real problem.
- Clear: optimize for the next reader, not for cleverness.
- Decoupled: keep boundaries clean, but do not add abstractions without a real need.
- Honest: make complexity, state, side effects, assumptions, and failure modes visible.
- Focused: preserve the small launcher model and keep top-level commands minimal.
- Durable: choose behavior that is easy to test and maintain.
- First principles: identify the real problem and hard constraints before adding concepts.

## Code Style

- Runtime language: Python 3.
- Package layout: `src/aweswitch/`.
- Keep the runtime dependency-free unless a dependency clearly earns its cost.
- Prefer small functions around config loading, profile resolution, argument preparation, and CLI commands.
- Keep user-facing errors actionable.
- Keep config examples valid JSON.
- Do not print raw secret values from `show` or `config show`.

## Config Semantics

The stable config shape is:

```json
{
  "profiles": {
    "claude": {
      "profile-name": {
        "env": {}
      }
    },
    "codex": {
      "profile-name": {
        "env": {}
      }
    }
  }
}
```

Current rules:

- `claude` and `codex` are executable providers.
- `profiles` must be a JSON object.
- Each provider group under `profiles` must be a JSON object.
- Each profile must be a JSON object.
- Profile `env` values must be JSON objects when present.
- Profile names must be unique across provider groups.
- Claude profiles are passed through runtime `--settings`; Codex profiles use `-c` flags and env vars.
- Environment references use `${VAR_NAME}`.
- Shell environment values take precedence over values loaded from `~/.claude/settings.json`.
- Invalid `~/.claude/settings.json` content is ignored by the current implementation. If a profile depends on values from that file, expect the later `${VAR_NAME}` expansion error to surface the missing variable.

## aweshelf Integration: How it Works

aweswitch supports auto-bookmarking sessions via [aweshelf](https://github.com/wehuman01/aweshelf) using `-c` (category) and `-t` (title) flags.

### Architecture

```
aweswitch process
  ├─ _auto_bookmark() → os.fork()
  │    └─ child process (background, no terminal)
  │         poll ~/.claude/projects/**/*.jsonl every 2s (max 60s)
  │         find new JSONL → aweshelf bookmark <id> -c <cat> --profile <p>
  │         os._exit(0)
  │
  └─ prepare_run() → execvpe("claude")
       └─ aweswitch process replaced by claude
```

Key design decisions:

- **Fork before exec**: `execvpe` replaces the process, so bookkeeping must happen in a child process spawned before exec.
- **CLI coupling, not import coupling**: the child calls `aweshelf bookmark` via `subprocess.run`, not by importing aweshelf internals. This keeps the tools decoupled at the code level.
- **File modification time as signal**: the child filters JSONL files by `st_mtime >= fork_time`. This is the only reliable way to identify "the session I just started" without knowing the session ID in advance.
- **Graceful degradation**: if aweshelf is not installed, `-c`/`-t` are ignored with a warning. Claude launches normally.

### Known Limitation: Concurrent Launch Race Condition

When multiple `aweswitch -c` processes are launched simultaneously in the same project directory, there is a chance of bookmarking the wrong session.

Example:

```bash
# Terminal 1                              # Terminal 2
aweswitch cc-glm -c backend               aweswitch cc-glm -c frontend
```

Both child processes scan the same `~/.claude/projects/` directory. When two new JSONL files appear, each child grabs the first file it encounters via `rglob`. Since directory traversal order is not deterministic, child A might grab child B's session and vice versa.

**Why it can't be fully fixed**: the session ID is assigned by Claude Code after launch. At fork time, aweswitch has no way to know which JSONL file will belong to its session. There is no identifier that can be passed from the parent to the child and matched against the JSONL content.

**Mitigations**:

- The child only considers files created after the fork (`st_mtime >= start_time`), which eliminates stale-file collisions.
- In practice, manually launching two sessions within the same 2-second poll window in the same project is uncommon.
- If you need concurrent launches with correct bookmarking, use `aweshelf bookmark` manually after the sessions start.

## Documentation

If you change command behavior, config shape, supported providers, or install steps, update the relevant docs in the same change:

- `README.md`
- `README_cn.md`
- `docs/CHANGELOG.md`
- tests that define the behavior

## Testing

Before committing, run:

```bash
python3 tests/test_aweswitch.py
python3 -m py_compile src/aweswitch/cli.py tests/test_aweswitch.py
```

If a change affects command output or config parsing, add or update tests in `tests/test_aweswitch.py`.

## Releasing

Releases are automated through GitHub Actions. The release path is:

1. Prepare release changes on `dev`.
2. Merge `dev` into `main`.
3. Push a `v*` tag from `main`.
4. Let `.github/workflows/release.yml` create the GitHub Release and publish to PyPI.

Before tagging a release:

- Update `pyproject.toml` and `src/aweswitch/__init__.py` to the target version.
- Update release-sensitive README references, including version badges and wheel examples.
- Add a top-level `## vX.Y.Z` entry to `docs/CHANGELOG.md`.
- Verify the tag name matches the package version, for example `v0.1.4` for version `0.1.4`.
- Confirm the repository has `PYPI_API_TOKEN` configured as a GitHub Actions secret.

Recommended local checks:

```bash
python3 -m unittest discover -s tests
python3 -m py_compile src/aweswitch/cli.py tests/test_aweswitch.py
python3 -m build
python3 -m twine check dist/*
```

The release workflow intentionally fails if it cannot find the matching changelog entry. Do not manually create the GitHub Release for a tagged release; the workflow owns that step.

## Questions

When in doubt, keep the change smaller. A focused fix or documentation improvement is better than a broad rewrite.
