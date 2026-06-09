# Context Notes

## 2026-06-08

- Decision: Treat WSL support for `mat` as the first deliverable and native Windows support as a follow-up in the separate `mat` repository.
- Reasoning: `multi-agent-starter` only generates the file structure that `mat` reads. The `mat` executable and any terminal/path portability fixes belong in `netwaif/mat`.
- Current repository remote layout: `origin` points to `EhEo/multi-agent-starter`; `upstream` fetches from `netwaif/multi-agent-starter` and has push disabled.
- Documentation update: Root README and all three generated flavor README templates now recommend WSL for Windows `mat` usage and keep native `mat.exe` as a future `mat` repository deliverable.
- Verification: `python tests\test_generate.py` and `python tests\test_update_preserve.py` passed. `bash tests/run.sh` failed before running tests because the Windows checkout has CRLF shell scripts. `validate.py --repo-check` also failed on a pre-existing repo-root assumption and CP949 output encoding, not on the README changes.
- WSL check: WSL2 Ubuntu is installed, but `mat`, `brew`, `go`, and `jq` were not present. WSL also prints a `.wslconfig` warning on startup, so actual `mat` execution needs WSL toolchain setup first.
- Upstream `mat` check: `netwaif/mat` exists, default branch is `main`, and the primary language is Go. No GitHub releases were listed by `gh release list`.
- `mat` fork: Created `EhEo/mat`, cloned it to `D:\GitRepos\mat`, added `upstream=https://github.com/netwaif/mat.git`, and disabled upstream push.
- Native Windows first change: `D:\GitRepos\mat` commit `e506d03` updates UI path shortening to handle `\` separators and adds experimental PowerShell build/run documentation.
- Native Windows verification: Downloaded official portable Go `go1.26.4.windows-amd64.zip` to `C:\tmp`, verified SHA-256, ran `gofmt`, `go test ./...`, and `go build -o mat.exe .` in `D:\GitRepos\mat`. Tests and build passed.
- Interactive smoke setup: Generated codex starter root at `C:\tmp\mat-smoke-starter`, added sample task `tasks/mat-smoke`, launched `D:\GitRepos\mat\mat.exe mat-smoke` in Windows Terminal with `MAT_ROOT=C:\tmp\mat-smoke-starter`, and confirmed the `mat` process stayed running.
- Follow-up plan: User should visually confirm Windows Terminal rendering, `L` log modal, `t` task modal, refresh, and quit behavior. After that, decide whether to add CI/release automation for Windows artifacts.

## 2026-06-09

- Decision: Use the same launcher name, `bin/multiagent`, on the `windows-version` branch. This does not conflict while Linux and Windows work stay on separate branches. A later merge can either keep one cross-platform launcher or split OS-specific launchers.
- Windows launcher target: Git Bash plus tmux, with native Windows `mat.exe` in the right pane. The launcher must convert Git Bash paths such as `/d/GitRepos/app` to Windows paths such as `D:\GitRepos\app` for generator and `MAT_ROOT`.
- Implementation: Added Windows/Git Bash `bin/multiagent`, which supports `-claude`, `-codex`, `--target`, `--setup-only`, `--no-mat`, and `--mat PATH`. It creates `_local/bin/mat-here` and passes native Windows `MAT_ROOT` to `mat.exe`.
- Verification: `python tests\test_multiagent_windows_launcher.py`, `python tests\test_generate.py`, and `python tests\test_update_preserve.py` passed. `C:\Program Files\Git\bin\bash.exe -n bin\multiagent` passed.
