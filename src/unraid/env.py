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
    _settings: dict[str, "SettingsDictT"]
    _env: dict[str, str]

    def __init__(
        self, prefix: str = PREFIX, *, data: None | dict[str, str] = None
    ) -> None:
        if data is None:
            data = os.environ

        self._prefix = prefix.casefold()
        self._env = {}
        self._settings = {}

        for key, value in data.items():
            key = key.casefold()
            self._env[key] = value

            match re.split(r"_{2,}", key):
                case [fst, *rst, lst] if fst.casefold() == self._prefix and rst:
                    current = self._settings
                    while rst:
                        current = current.setdefault(rst[0], {})
                        rst = rst[1:]
                    current[lst] = value

    def settings_keys(self) -> t.Iterator[str]:
        return iter(self._settings)

    def all_keys(self) -> t.Iterator[tuple[str, ...]]:
        def rec_iter(dct: SettingsDictT) -> t.Iterator[tuple[str, ...]]:
            if isinstance(dct, dict):
                for key, value in dct.items():
                    for subkey in rec_iter(value):
                        yield (key, *subkey)

        for key in rec_iter(self._settings):
            yield (self._prefix, *key)
        for key in self._env:
            yield (key,)

    def __repr__(self) -> str:
        return repr(
            {
                "prefix": self._prefix,
                "settings": self._settings,
                # "env": self._env,
            }
        )

    def get(self, *path: str, default: str = "") -> str:
        match len(path):
            case 0:
                raise ValueError("Empty path is forbidden")
            case 1:
                return self._env.get(path[0], default)

        current = self._settings
        try:
            for elem in path[:-1]:
                current = current[elem]
            return current.get(path[-1], default)
        except Exception as exc:
            key = [self._prefix, *path]
            raise KeyError(f"Cannot get a key {'__'.join(key)}") from exc
