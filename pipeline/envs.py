"""Run a command inside a conda environment, correctly and interruptibly.

Uses `conda run -n <env>` rather than PATH-prepending. PATH-prepending (what
the old stage-5/7 python scripts did) skips each package's activate.d hooks
entirely — e.g. funannotate's PASAHOME and AUGUSTUS_CONFIG_PATH are set by
`envs/funannotate/etc/conda/activate.d/pasa-2.5.3.sh` and `augustus.sh`, not
by anything on PATH. `conda run` executes those hooks; a bare PATH prepend
silently doesn't, which is why the old code had to hand-set PASAHOME as a
workaround for one variable while leaving anything else the hooks set
unhandled.
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import time
from pathlib import Path

CONDA_EXE = "/opt/miniconda3/condabin/conda"
logger = logging.getLogger("pipeline.envs")


class CommandFailed(RuntimeError):
    def __init__(self, cmd: list[str], returncode: int, log_file: Path):
        self.cmd = cmd
        self.returncode = returncode
        self.log_file = log_file
        super().__init__(
            f"command exited {returncode}: {' '.join(cmd)} (see {log_file})"
        )


def run_in_env(
    cmd: list[str],
    env_name: str,
    log_file: Path,
    cwd: Path | None = None,
    extra_env: dict[str, str] | None = None,
    check: bool = True,
) -> int:
    """Run `cmd` inside conda env `env_name`, streaming output to log_file.

    Builds the environment from a fresh os.environ.copy() every call, never
    a shared/mutated dict, so one stage's overrides can't leak into the next
    stage's subprocess in a long-lived orchestrator process.
    """
    full_cmd = [CONDA_EXE, "run", "-n", env_name, "--no-capture-output", *cmd]
    return _run_streamed(full_cmd, log_file, cwd=cwd, extra_env=extra_env, check=check)


def run_system(
    cmd: list[str],
    log_file: Path,
    cwd: Path | None = None,
    extra_env: dict[str, str] | None = None,
    check: bool = True,
) -> int:
    """Run `cmd` on the plain system PATH — for tools that aren't a conda
    env (e.g. InterProScan, installed standalone at a fixed path)."""
    return _run_streamed(cmd, log_file, cwd=cwd, extra_env=extra_env, check=check)


def _run_streamed(
    full_cmd: list[str],
    log_file: Path,
    cwd: Path | None,
    extra_env: dict[str, str] | None,
    check: bool,
) -> int:
    """Shared subprocess-streaming implementation.

    Launches the child in its own process group (start_new_session=True) so
    that on interrupt we can kill the whole tree — funannotate/InterProScan
    spawn grandchildren (Trinity/Augustus/GeneMark/Java workers) that would
    otherwise survive a plain Popen.terminate() and keep burning CPU/RAM.
    """
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)

    log_file.parent.mkdir(parents=True, exist_ok=True)

    with open(log_file, "a", encoding="utf-8") as log_fh:
        log_fh.write(f"\n$ {' '.join(full_cmd)}\n")
        log_fh.flush()

        process = subprocess.Popen(
            full_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=cwd,
            env=env,
            start_new_session=True,
        )
        try:
            assert process.stdout is not None
            for line in process.stdout:
                print(line, end="", flush=True)
                log_fh.write(line)
            process.wait()
        except BaseException:
            _kill_process_group(process)
            raise

    returncode = process.returncode
    if check and returncode != 0:
        raise CommandFailed(full_cmd, returncode, log_file)
    return returncode


def _group_is_alive(pgid: int) -> bool:
    """`killpg(pgid, 0)` sends no signal, just checks whether any process in
    the group still exists (and that we have permission to signal it)."""
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False


def _kill_process_group(process: subprocess.Popen) -> None:
    """Kill the whole process group, and verify it actually emptied.

    Waiting on `process` alone (the direct child, typically `conda run`) is
    not sufficient: a grandchild the direct child spawned (e.g. a tool's own
    worker subprocess) can outlive it, especially if a signal arrives while
    that grandchild is in an uninterruptible disk-wait (D state) — in which
    case *no* signal, not even SIGKILL, has any effect until its blocking
    syscall returns. That's a kernel-level limitation this code can't
    override; the best it can do is not silently claim success when a
    process is still there.
    """
    if process.poll() is not None:
        return
    try:
        pgid = os.getpgid(process.pid)
    except ProcessLookupError:
        return

    os.killpg(pgid, signal.SIGTERM)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pass

    if not _group_is_alive(pgid):
        return

    logger.warning("process group %d still alive after SIGTERM, escalating to SIGKILL", pgid)
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        return

    for _ in range(10):
        if not _group_is_alive(pgid):
            return
        time.sleep(1)

    logger.error(
        "process group %d survived SIGKILL — likely stuck in an uninterruptible "
        "(D-state) syscall; it will only exit once that syscall returns, which "
        "no signal can force. Check `ps -o pid,stat,cmd -g %d` manually.",
        pgid,
        pgid,
    )
