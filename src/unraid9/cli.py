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
import datetime
import functools
import logging
import os
import random
import signal
import sys
import textwrap
import threading
import typing as t

import croniter

from unraid9 import env


if t.TYPE_CHECKING:
    T = t.TypeVar("T")
    P = t.ParamSpec("P")


LOG: t.Final = logging.getLogger(__name__)
STOP: t.Final = threading.Event()


def main(
    doc: str,
) -> t.Callable[
    [t.Callable[[contextlib.ExitStack, env.EnvDict], None]],
    t.Callable[[], None],
]:
    doc = doc.strip()
    doc = textwrap.dedent(doc)

    def outer_decorator(
        func: t.Callable[[contextlib.ExitStack, env.EnvDict], None],
    ) -> t.Callable[[], None]:
        @functools.wraps(func)
        def inner_decorator() -> None:
            logging.basicConfig(
                format="%(asctime)s [%(levelname)s] %(message)s",
                level=logging.DEBUG,
                # unraid ios app expects stdout, so why not
                stream=sys.stdout,
            )

            argparse.ArgumentParser(
                description=doc.splitlines()[0].rstrip(),
                formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            ).parse_args()

            LOG.info("--- Start")

            settings = env.parse(os.environ)
            LOG.debug("Settings: %r", settings)

            for sig in signal.SIGINT, signal.SIGTERM:
                signal.signal(sig, signal_stop)

            with contextlib.ExitStack() as estack:
                func(estack, settings)

            LOG.info("--- Stop")

        return inner_decorator

    return outer_decorator


def repeat_until_stop(
    name: str, schedule: str
) -> t.Callable[
    [t.Callable[t.Concatenate[contextlib.ExitStack, P], T]],
    t.Callable[P, t.Never],
]:
    def now() -> datetime.datetime:
        return datetime.datetime.now(datetime.timezone.utc)

    def time_iterate() -> t.Iterator[int | float]:
        sleep_for = random.randint(0, 180)
        next_time = now() + datetime.timedelta(seconds=sleep_for)

        LOG.info("Wait %s for %d seconds (at %s)", name, sleep_for, next_time)
        yield sleep_for

        cron = croniter.croniter(schedule, now())
        while True:
            next_time = cron.get_next(datetime.datetime)
            LOG.info("Execute %s at %s", name, next_time)
            yield (next_time - now()).total_seconds()

    def outer_decorator(
        func: t.Callable[t.Concatenate[contextlib.ExitStack, P], T],
    ) -> t.Callable[P, t.Never]:
        @functools.wraps(func)
        def inner_decorator(*args: P.args, **kwargs: P.kwargs) -> t.Never:  # type: ignore[bad-return]
            timer = time_iterate()
            while not STOP.wait(next(timer)):
                with (
                    contextlib.suppress(Exception),
                    contextlib.ExitStack() as estack,
                ):
                    func(estack, *args, **kwargs)

        return inner_decorator

    return outer_decorator


def signal_stop(signum: int, _: t.Any) -> None:  # noqa: ANN401
    signame = signal.Signals(signum).name
    LOG.info("Caught %s", signame)
    STOP.set()
