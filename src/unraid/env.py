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

import os
import re
import typing as t


if t.TYPE_CHECKING:
    SettingsDictT = str | dict[str, "SettingsDictT"]


PREFIX: t.Final = "SETTING"


class Env:
    _prefix: str
    _data: dict[str, "SettingsDictT"]

    def __init__(
        self, prefix: str = PREFIX, *, data: dict[str, str] | None = None
    ) -> None:
        if data is None:
            data = os.environ

        self._prefix = prefix.casefold()
        self._data = {}

        for key, value in data.items():
            key = key.casefold()

            match re.split(r"_{2,}", key):
                case [self._prefix, *rst, lst]:
                    current = self._data
                    while rst:
                        current = current.setdefault(rst[0], {})
                        rst = rst[1:]
                    current[lst] = value

    def get(self, path: str, *paths: str, default: str = "") -> str:
        current = self._data[path.casefold()]
        rv = ""

        if paths:
            for elem in paths[1:]:
                current = current[elem.casefold()]
            rv = current.get(paths[-1], default)

        if not isinstance(rv, str):
            raise KeyError("Umbigous path")

        return rv

    def __iter__(self) -> t.Iterator[tuple[str, ...]]:
        def rec_iter(value: SettingsDictT) -> t.Iterator[list[str]]:
            if isinstance(value, str):
                yield ()
            else:
                yield from (
                    [k, *subkey]
                    for k, v in value.items()
                    for subkey in rec_iter(v)
                )

        for elem in rec_iter(self._data):
            yield tuple(elem)
