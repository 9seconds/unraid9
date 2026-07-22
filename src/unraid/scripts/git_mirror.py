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

This script is configured by environment variables masked as `MIRROR_*_{URL,SCHEDULE,ARCHIVE}`.
For example:

* `MIRROR_DOTFILES_URL = git@github.com/9seconds/dotfiles.git`
* `MIRROR_DOTFILES_ARCHIVE = dotfiles`
* `MIRROR_DOTFILES_SCHEDULE = "0 * * * * *"`
"""  # noqa: E501

PATH_ARCHIVES: t.Final = pathlib.Path("/archives")
PATH_WORK: t.Final = pathlib.Path("/work")

LOG: t.Final = logging.getLogger(__name__)


@cli.main(DOC)
def main(estack: contextlib.ExitStack, settings: env.Env) -> None:
    PATH_WORK.mkdir(exist_ok=True, parents=True)
    PATH_ARCHIVES.mkdir(exist_ok=True, parents=True)

    private_key = settings.get("setting_sshkey").strip()
    if not private_key:
        raise ValueError("Private key must be defined")

    with tempfile.NamedTemporaryFile(delete=False) as fp:
        fp.write(base64.standard_b64decode(private_key.encode()))

    ssh_private_key_path = pathlib.Path(fp.name).absolute()
    ssh_private_key_path.chmod(0o400)
    estack.callback(ssh_private_key_path.unlink)

    git_exec = functools.partial(
        cmd.cmd_exec,
        "git",
        env={
            "GIT_SSH_COMMAND": subprocess.list2cmdline(
                ["ssh", "-i", os.fspath(ssh_private_key_path)]
            )
        },
    )

    threads: list[threading.Thread] = []

    for group in settings.settings_keys():
        url = settings.get(group, "url")
        if not url:
            raise ValueError(f"{group}: url must be defined")

        url_to_validate = url
        if url_to_validate.startswith("git@"):
            url_to_validate = f"ssh://{url_to_validate}"
        validators.url(url_to_validate)

        archive_name = settings.get(
            group, "archive", default=pathlib.Path(url).with_suffix("").name
        )
        validators.slug(archive_name)

        schedule = croniter.croniter(
            settings.get(group, "schedule", default="R R * * *")
        )

        threads.append(
            threading.Thread(
                target=process, args=(git_exec, url, archive_name, schedule)
            )
        )

    for sig in signal.SIGINT, signal.SIGTERM:
        signal.signal(sig, signal_stop)

    for th in threads:
        th.start()

    for th in threads:
        th.join()


def process(
    git_func: GitCallable,
    url: str,
    archive_name: str,
    schedule: croniter.croniter,
) -> None:
    work_path = PATH_WORK / archive_name

    while True:
        next_execution = schedule.get_next(ret_type=datetime.datetime)
        LOG.info("Process %s (to %s) at %s", url, work_path, next_execution)

        to_sleep = (next_execution - datetime.datetime.now()).total_seconds()
        if EVT_STOP.wait(to_sleep):
            return

        with contextlib.suppress(subprocess.CalledProcessError):
            if not work_path.exists():
                git_func(
                    "clone", "--quiet", "--mirror", "--tags", url, work_path
                )

            git_func = functools.partial(git_func, "--git-dir", work_path)
            git_func("remote", "update", "--prune")
            git_func("gc", "--auto", "--aggressive", "--quiet")

            cmd.cmd_exec(
                "tar",
                "-cJ",
                "-f",
                PATH_ARCHIVES.joinpath(archive_name).with_suffix(".tar.xz"),
                "-C",
                work_path,
                ".",
                env={"XZ_OPT": "-9 -T 0"},
            )


def signal_stop(signum: int, frame: t.Any) -> None:  # noqa: ANN401, ARG001
    signame = signal.Signals(signum).name
    LOG.info("Caught %s", signame)
    EVT_STOP.set()
