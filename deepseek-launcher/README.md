# Shared DeepSeek launcher

`deepcode-run.sh` is the supported Doppler-backed launcher for `deepseek` and
`deepcode`. It owns the temporary `~/.deepcode/settings.json` required by the
DeepCode CLI. The key is only fetched from Doppler. New files have mode `0600`;
normal exit, fetch failure, and catchable termination clear the file before
moving it to Trash. An existing handwritten settings file is left untouched.

When `-x` runs without a terminal, the launcher uses
`deepseek-pty-exec.py` automatically. It starts in the caller's current
directory and has a 300-second deadline by default. Set `DEEPCODE_TIMEOUT`
to a positive number of seconds for another deadline. The helper is also
callable directly with `--cwd`, `--timeout`, and `-p`.

To install on a host after the PR is cleared, point `~/bin/deepseek`,
`~/bin/deepcode`, and `~/bin/deepseek-pty` at the corresponding files in this
directory. The CLI executable named `deepcode` must also be installed
elsewhere on `PATH` (such as a package-manager installation).

Run synthetic checks with:

```sh
python3 -m unittest discover -s deepseek-launcher -p 'test_*.py' -v
```

`SIGKILL` and machine power loss cannot run the exit handler. A following
launch detects a dead owner and clears the stale credential before starting.
Do not use the Trash for a handwritten settings file containing a key.
