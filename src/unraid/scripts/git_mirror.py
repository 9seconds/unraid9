# MIT License
#
# Copyright (c) 2026 Sergei Arkhipov
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from __future__ import annotations

import base64
import contextlib
import datetime
import functools
import logging
import os
import pathlib
import signal
import subprocess
import tempfile
import threading
import typing as t

import croniter
import validators

from unraid import cli
from unraid import cmd


if t.TYPE_CHECKING:
    import contextlib

    from unraid import env

    class GitCallable(t.Protocol):
        def __call__(self, *command: str) -> None: ...


EVT_STOP: t.Final = threading.Event()


DOC: t.Final = """
This command mirrors git repositories.

This script is configured by environment variables masked as
`SETTING__*__{URL,SCHEDULE,ARCHIVE}`. For example:

* `SETTING__DOTFILES__URL = git@github.com/9seconds/dotfiles.git`
* `SETTING__DOTFILES__STEM = dotfiles`
* `SETTING__DOTFILES__SCHEDULE = "0 * * * * *"`

Also, there are path directories:

* `SETTING__WORK_DIR = /work`
* `SETTING__ARCHIVES_DIR = /archives`
* `SETTING__SSH_PRIVATE_KEY = ...`
"""

LOG: t.Final = logging.getLogger(__name__)


@cli.main(DOC)
def main(estack: contextlib.ExitStack, settings: env.Env) -> None:
    private_key = settings.get("ssh_private_key").strip()
    if not private_key:
        raise ValueError("Private key must be defined")

    fd, path_ = tempfile.mkstemp()
    os.write(fd, base64.standard_b64decode(private_key.encode()))
    os.close(fd)

    ssh_private_key_path = pathlib.Path(path_)
    ssh_private_key_path.chmod(0o400)
    estack.callback(ssh_private_key_path.unlink, missing_ok=True)

    work_dir = pathlib.Path(settings.get("work_dir", default="/work"))
    work_dir.mkdir(exist_ok=True, parents=True)

    archives_dir = pathlib.Path(
        settings.get("archives_dir", default="/archives")
    )
    archives_dir.mkdir(exist_ok=True, parents=True)

    git_exec = functools.partial(
        cmd.cmd_exec,
        "git",
        env={
            "GIT_SSH_COMMAND": subprocess.list2cmdline(
                [
                    "ssh",
                    "-i",
                    os.fspath(ssh_private_key_path),
                    "-o",
                    "StrictHostKeyChecking=accept-new",
                ]
            )
        },
    )

    threads: list[threading.Thread] = []

    for group in {k[0] for k in settings if len(k) > 1 and k[1] == "url"}:
        url = settings.get(group, "url")
        if url.startswith("git@"):
            validators.url(f"ssh://{url}")
        else:
            validators.url(url)

        stem = settings.get(
            group, "stem", default=pathlib.Path(url).with_suffix("").name
        )
        validators.slug(stem)

        threads.append(
            threading.Thread(
                target=process_url,
                kwargs={
                    "git_exec": git_exec,
                    "url": url,
                    "work_path": work_dir / stem,
                    "archive_path": archives_dir.joinpath(stem).with_suffix(
                        ".tar.xz"
                    ),
                    "schedule": croniter.croniter(
                        settings.get(group, "schedule", default="R R * * *")
                    ),
                },
            )
        )

    for sig in signal.SIGINT, signal.SIGTERM:
        signal.signal(sig, signal_stop)

    for th in threads:
        th.start()

    for th in threads:
        th.join()


def process_url(
    *,
    url: str,
    work_path: pathlib.Path,
    archive_path: pathlib.Path,
    schedule: croniter.croniter,
    git_exec: GitCallable,
) -> None:
    while True:
        next_execution = schedule.get_next(ret_type=datetime.datetime)
        LOG.info("Process %s (to %s) at %s", url, work_path, next_execution)

        to_sleep = (next_execution - datetime.datetime.now()).total_seconds()
        if EVT_STOP.wait(to_sleep):
            return

        with contextlib.ExitStack() as estack:
            create_archive(
                url=url,
                work_path=work_path,
                archive_path=archive_path,
                estack=estack,
                git_exec=git_exec,
            )


def create_archive(
    *,
    url: str,
    work_path: pathlib.Path,
    archive_path: pathlib.Path,
    estack: contextlib.ExitStack,
    git_exec: GitCallable,
) -> None:
    estack.enter_context(contextlib.suppress(subprocess.CalledProcessError))

    if not work_path.exists():
        git_exec("clone", "--quiet", "--mirror", "--tags", url, work_path)
    else:
        git_exec = functools.partial(git_exec, "--git-dir", work_path)
        git_exec("remote", "update", "--prune")
        git_exec("gc", "--auto", "--aggressive", "--quiet")

    fd, path_ = tempfile.mkstemp(
        dir=archive_path.parent, prefix=f".{archive_path.name}."
    )
    os.close(fd)

    tmp_path = pathlib.Path(path_)
    estack.callback(tmp_path.unlink, missing_ok=True)

    cmd.cmd_exec(
        "tar",
        "-cJ",
        "-f",
        tmp_path,
        "-C",
        work_path,
        ".",
        env={"XZ_OPT": "-9 -T 0"},
    )
    tmp_path.rename(archive_path)


def signal_stop(signum: int, _: t.Any) -> None:  # noqa: ANN401
    signame = signal.Signals(signum).name
    LOG.info("Caught %s", signame)
    EVT_STOP.set()
