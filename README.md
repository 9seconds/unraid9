# unraid9

This is a project for several scripts I use for "scripts" that I run on my home
NAS. This NAS is running [unraid](https://unraid.net/), so it names a project.

# git-mirror

This projects helps to synchronize git repositories and maintain a local
mirrors. Its goal is to create an archive.

This script is configured by environment variables masked as
`SETTING__*__{URL,SCHEDULE,ARCHIVE}`. For example:

* `SETTING__DOTFILES__URL = git@github.com/9seconds/dotfiles.git`
* `SETTING__DOTFILES__STEM = dotfiles`
* `SETTING__DOTFILES__SCHEDULE = "0 * * * * *"`

Also, there are path directories:

* `SETTING__WORK_DIR = /work`
* `SETTING__ARCHIVES_DIR = /archives`
* `SETTING__SSH_PRIVATE_KEY = ...`

By default it logs to stdout.
