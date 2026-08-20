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

import contextlib
import logging
import os
import pathlib
import tempfile
import time
import typing as t

import validators

from unraid9 import cli
from unraid9 import cmd


if t.TYPE_CHECKING:
    from unraid9 import env


PREFIX: t.Final = "SETTING"
DOC: t.Final = f"""
This is a wrapper for yt-dlp to download youtube as audio podcasts

Configuration is:

* `{PREFIX}__WORK_DIR = /work` - directory with own data
* `{PREFIX}__ARCHIVES_DIR = /archives` - where to store audio files
* `{PREFIX}__DATE_AFTER = today-1week` - start date to examine
* `{PREFIX}__CLEANUP_AFTER_DAYS = 60` - how many days to cleanup for the files

* `{PREFIX}__URL__* = https://...` - contains URL of the media to download
"""

LOG: t.Final = logging.getLogger(__name__)


@cli.main(DOC)
def main(es: contextlib.ExitStack, settings: env.EnvDict) -> None:
    work_dir = pathlib.Path(settings.get(("setting", "work_dir"), "/work"))
    work_dir.mkdir(exist_ok=True, parents=True)

    archives_dir = pathlib.Path(
        settings.get(("setting", "archives_dir"), "/archives")
    )
    archives_dir.mkdir(exist_ok=True, parents=True)

    date_after = settings.get(("setting", "date_after"), "today-1week")
    cleanup_after = abs(
        int(settings.get(("setting", "cleanup_after_days"), "60"))
    )

    urls: list[str] = []
    for group, value in settings.items():
        match group:
            case ["setting", "url", _]:
                validators.url(value, r_ve=True)
                urls.append(value)

    fd, urls_file = tempfile.mkstemp(text=True)
    for url in set(urls):
        os.write(fd, f"{url}\n".encode())
    os.close(fd)
    es.callback(os.unlink, urls_file)

    execute(
        work_dir=work_dir,
        archives_dir=archives_dir,
        date_after=date_after,
        cleanup_after=cleanup_after,
        urls_file=urls_file,
    )


@cli.repeat_until_stop("yt-dlp", "R * * * *")
def execute(
    _: contextlib.ExitStack,
    *,
    work_dir: pathlib.Path,
    archives_dir: pathlib.Path,
    date_after: str,
    cleanup_after: int,
    urls_file: str,
) -> None:
    cmd.cmd_exec(
        "yt-dlp",
        # Do not load any custom configuration files (default).
        # When given inside a configuration file, ignore all previous
        # --config-locations defined in the current file
        "--no-config-locations",
        # Whether to emit color codes in output, optionally prefixed
        # by the STREAM (stdout or stderr) to apply the setting to.
        # Can be one of "always", "auto" (default), "never", or
        # "no_color" (use non color terminal sequences). Use
        # "auto-tty" or "no_color-tty" to decide based on terminal
        # support only. Can be used multiple times
        "--color",
        "no_color",
        # Client to impersonate for requests. E.g.
        # chrome, chrome-110, chrome:windows-10.
        # Pass --impersonate="" to impersonate any client.
        # Note that forcing impersonation for all requests may have
        # a detrimental impact on download speed and stability
        "--impersonate",
        "chrome",
        # Download only videos uploaded on or after this date.
        # The date formats accepted are the same as --date
        # The date can be "YYYYMMDD" or in the format
        # [now|today|yesterday][-N[day|week|month|year]].
        # E.g. "--date today-2weeks" downloads only videos
        # uploaded on the same day two weeks ago
        "--dateafter",
        date_after,
        # Use --break-match-filters
        "--break-on-reject",
        # Reset break behavior for each URL in the batch file so an older
        # video in one channel does not stop later channels from processing.
        "--break-per-input",
        # Minimum download rate in bytes per second below which
        # throttling is assumed and the video data is re-extracted,
        # e.g. 100K
        "--throttled-rate",
        "128K",
        # Time to sleep between retries in seconds (optionally)
        # prefixed by the type of retry (http (default),
        # fragment, file_access, extractor) to apply the sleep to.
        # EXPR can be a number, linear=START[:END[:STEP=1]] or
        # exp=START[:END[:BASE=2]]. This option can be used
        # multiple times to set the sleep for the different retry types,
        # e.g. --retry-sleep linear=1::2 --retry-sleep fragment:exp=1:20
        "--retry-sleep",
        "exp=1:60",
        # Limit the filename length (excluding extension) to
        # the specified number of characters
        "--trim-filenames",
        "79",
        # Netscape formatted file to read cookies from and dump cookie
        # jar in
        "--cookies",
        work_dir / "cookies",
        # Location in the filesystem where yt-dlp can store some
        # downloaded information (such as client ids and signatures)
        # permanently.
        "--cache-dir",
        work_dir / "cache",
        # Do not print progress bar
        "--no-progress",
        # Do not print normal output; errors are still reported
        "--quiet",
        # Video format code, see "FORMAT SELECTION" for more details
        "--format",
        "bestaudio",
        # Convert video files to audio-only files (requires ffmpeg and
        # ffprobe)
        "--extract-audio",
        # Format to convert the audio to when -x is used. (currently
        # supported: best (default), aac, alac, flac, m4a, mp3, opus,
        # vorbis, wav). You can specify multiple rules using similar
        # syntax as --remux-video
        "--audio-format",
        "opus",
        # Specify ffmpeg audio quality to use when converting the audio
        # with -x. Insert a value between 0 (best) and 10 (worst) for
        # VBR or a specific bitrate like 128K (default 5)
        "--audio-quality",
        "9",
        # Embed thumbnail in the video as cover art
        "--embed-thumbnail",
        # Preserve the upload time so AudioBookShelf can order same-day
        # episodes.
        "--parse-metadata",
        r"%(timestamp>%Y-%m-%dT%H\:%M\:%SZ)s:meta_date",
        # Embed metadata to the video file. Also embeds
        # chapters/infojson if present unless
        # --no-embed-chapters/--no-embed-info-json are used
        # (Alias: --add-metadata)
        "--embed-metadata",
        # Add chapter markers to the video file (Alias: --add-chapters)
        "--embed-chapters",
        # Download only videos not listed in the archive file.
        # Record the IDs of all downloaded videos in it
        "--download-archive",
        work_dir / "download-archive.txt",
        # File containing URLs to download ("-" for stdin), one URL per
        # line. Lines starting with "#", ";" or "]" are considered
        # as comments and ignored
        "--batch-file",
        urls_file,
        # Output filename template; see "OUTPUT TEMPLATE" for details
        "--output",
        "%(channel,uploader)s/%(upload_date)s - %(title)s.%(ext)s",
        # The paths where the files should be downloaded. Specify
        # the type of file and the path separated by a colon ":".
        # All the same TYPES as --output are supported.
        # Additionally, you can also provide "home" (default) and
        # "temp" paths. All intermediary files are first downloaded
        # to the temp path and then the final files are moved over to
        # the home path after download is finished. This option is
        # ignored if --output is an absolute path
        "--paths",
        archives_dir,
    )

    delete_after = time.time() - (cleanup_after * 24 * 60 * 60)
    to_delete = [
        path
        for dirpath, _, filenames in archives_dir.walk()
        for name in filenames
        if (path := dirpath / name).stat().st_mtime < delete_after
    ]
    to_delete.sort(reverse=True)

    for path in to_delete:
        with contextlib.suppress(OSError):
            path.unlink(missing_ok=True)
        LOG.info("Deleted %s", path)

        cdir = path
        while (cdir := cdir.parent) != archives_dir and not any(cdir.iterdir()):
            with contextlib.suppress(OSError):
                cdir.rmdir()
            LOG.info("Deleted %s", cdir)
