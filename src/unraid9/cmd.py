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

import logging
import os
import subprocess
import textwrap
import typing as t


if t.TYPE_CHECKING:
    import pathlib


LOG: t.Final = logging.getLogger(__name__)


def cmd_exec(
    *command: str | pathlib.Path, env: dict[str, str] | None = None
) -> list[str]:
    str_cmd = subprocess.list2cmdline(command)
    str_cmd = textwrap.shorten(str_cmd, 79)

    env = env or {}

    proc = subprocess.run(
        command,
        text=True,
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**env, **os.environ},
    )

    LOG.debug("%s: rc=%d", str_cmd, proc.returncode)

    stdout = proc.stdout.splitlines()
    for line in stdout:
        LOG.debug("%s: stdout: %s", str_cmd, line)

    for line in proc.stderr.splitlines():
        LOG.debug("%s: stderr: %s", str_cmd, line)

    if proc.returncode != 0:
        raise subprocess.CalledProcessError(
            proc.returncode, proc.args, output=proc.stdout, stderr=proc.stderr
        )

    return stdout
