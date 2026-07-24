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
import collections
import contextlib
import functools
import logging
import os
import pathlib
import subprocess
import tempfile
import threading
import typing as t

import croniter
import validators

from unraid9 import cli
from unraid9 import cmd


if t.TYPE_CHECKING:
    import contextlib

    from unraid9 import env

    class GitCallable(t.Protocol):
        def __call__(self, *command: str | pathlib.Path) -> None: ...


PREFIX: t.Final = "SETTING"
DOC: t.Final = f"""
This command mirrors git repositories.

This script is configured by environment variables masked as
`{PREFIX}__*__{{URL,SCHEDULE,ARCHIVE}}`. For example:

* `{PREFIX}__DOTFILES__URL = git@github.com:9seconds/dotfiles.git`
* `{PREFIX}__DOTFILES__STEM = dotfiles`
* `{PREFIX}__DOTFILES__SCHEDULE = "0 * * * * *"`

Also, there are path directories:

* `{PREFIX}__WORK_DIR = /work`
* `{PREFIX}__ARCHIVES_DIR = /archives`
* `{PREFIX}__SSH_PRIVATE_KEY = ...`
"""

LOG: t.Final = logging.getLogger(__name__)


@cli.main(DOC)
def main(es: contextlib.ExitStack, settings: env.EnvDict) -> None:  # noqa: C901
    private_key = settings[("setting", "ssh_private_key")]
    if not private_key:
        raise ValueError("Private key must be defined")

    fd, path_ = tempfile.mkstemp()
    os.write(fd, base64.standard_b64decode(private_key.encode()))
    os.close(fd)

    ssh_private_key_path = pathlib.Path(path_)
    ssh_private_key_path.chmod(0o400)
    es.callback(ssh_private_key_path.unlink, missing_ok=True)

    work_dir = pathlib.Path(settings.get(("setting", "work_dir"), "/work"))
    work_dir.mkdir(exist_ok=True, parents=True)

    archives_dir = pathlib.Path(
        settings.get(("setting", "archives_dir"), "/archives")
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

    configs: collections.defaultdict[str, dict[str, str]] = (
        collections.defaultdict(dict)
    )

    for key, value in settings.items():
        match key:
            case ["setting", group, "url"]:
                configs[group]["url"] = value
            case ["setting", group, "stem"]:
                configs[group]["stem"] = value
            case ["setting", group, "schedule"]:
                configs[group]["schedule"] = value

    threads: list[threading.Thread] = []
    for name, config in configs.items():
        if "url" not in config:
            raise ValueError(f"{name}: url is not found")

        if "@" in (url := config["url"]):
            cred, path = url.split(":", maxsplit=1)
            validators.email(cred, r_ve=True)
            pathlib.Path(path)
        else:
            validators.url(url, r_ve=True)

        config.setdefault(
            "stem", pathlib.Path(config["url"]).with_suffix("").name
        )
        validators.slug(config["stem"], r_ve=True)

        config.setdefault("schedule", "R R * * *")
        if not croniter.croniter.is_valid(config["schedule"]):
            raise ValueError(f"{name}: invalid schedule")

        threads.append(
            threading.Thread(
                name=name,
                target=cli.repeat_until_stop(name, config["schedule"])(
                    create_archive
                ),
                kwargs={
                    "git_exec": git_exec,
                    "url": url,
                    "work_path": work_dir / config["stem"],
                    "archive_path": archives_dir.joinpath(
                        config["stem"]
                    ).with_suffix(".tar.gz"),
                },
            )
        )

    for th in threads:
        th.start()

    for th in threads:
        th.join()


def create_archive(
    estack: contextlib.ExitStack,
    *,
    url: str,
    work_path: pathlib.Path,
    archive_path: pathlib.Path,
    git_exec: GitCallable,
) -> None:
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

    cmd.cmd_exec("tar", "-cz", "-f", tmp_path, "-C", work_path, ".")
    tmp_path.rename(archive_path)
