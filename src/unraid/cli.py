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

import argparse
import contextlib
import functools
import logging
import textwrap
import typing as t

from unraid import env


LOG: t.Final = logging.getLogger(__name__)


def main(
    doc: str, prefix: str = env.PREFIX
) -> t.Callable[
    [t.Callable[[contextlib.ExitStack, env.Env], None]], t.Callable[[], None]
]:
    doc = doc.strip()
    doc = textwrap.dedent(doc)

    def outer_decorator(
        func: t.Callable[[contextlib.ExitStack, env.Env], None],
    ) -> t.Callable[[contextlib.ExitStack, env.Env], None]:
        @functools.wraps(func)
        def inner_decorator() -> None:
            logging.basicConfig(
                format="%(asctime)s [%(levelname)s] %(message)s",
                level=logging.DEBUG,
            )

            def print_usage(_s: contextlib.ExitStack, _e: env.Env) -> None:
                print(doc)  # noqa: T201

            parser = argparse.ArgumentParser(
                description=doc.splitlines()[0].rstrip(),
                formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            )
            parser.set_defaults(cmd=print_usage)

            subcommands = parser.add_subparsers(title="Commands")
            subcommands.add_parser(
                "usage",
                help="show usage",
                description="Show usage",
                formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            ).set_defaults(cmd=print_usage)
            subcommands.add_parser(
                "run",
                help="run command",
                description="Run command",
                formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            ).set_defaults(cmd=func)

            settings = env.Env(prefix)
            LOG.debug("Settings: %r", settings)

            with contextlib.ExitStack() as estack:
                parser.parse_args().cmd(estack, settings)

        return inner_decorator

    return outer_decorator
