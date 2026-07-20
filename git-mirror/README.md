# git-mirror

This projects helps to synchronize git repositories and maintain a local
mirrors. Its goal is to create an archive.

| Path            | Meaning                                                    |
| --------------- | ---------------------------------------------------------- |
| `/repositories` | A place where to store downloaded repositories (temporary) |
| `/archives`     | A place where to store archives of repositories            |

This script is configured by environment variables masked as `MIRROR_*_{URL,SCHEDULE,ARCHIVE}`.
For example:

* `MIRROR_DOTFILES_URL = git@github.com/9seconds/dotfiles.git`
* `MIRROR_DOTFILES_ARCHIVE = dotfiles`
* `MIRROR_DOTFILES_SCHEDULE = "0 * * * * *"`

A middle section is just a reference to the configuration section.

| Variable            | Meaning                                        | Default                        |
| ------------------- | ---------------------------------------------- | ------------------------------ |
| `MIRROR_*_URL`      | URL of the repository to mirror                | No default value               |
| `MIRROR_*_ARCHIVE`  | A stem of the archive.                         | Extracted from URL             |
| `MIRROR_*_SCHEDULE` | A crontab expression when to mirror an archive | Random hour/minutes of the day |

By default it logs to stdout.
