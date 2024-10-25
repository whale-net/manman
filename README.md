# manman
([cs2/game]server)man(ager)man(ager)


## about

successor of https://github.com/whale-net/cs-server-runner

more cloud friendly

hopefully better patterns

easier deployment (maybe?)

fun fact: according to https://en.wiktionary.org/wiki/manman, manman is mother in haitian creole, and is the act of observing in tagalog
this project is the mother and observer to all the little workers

### features

- runs servers in server manager service (manman-worker)
    - exposes management API (install/start/shutdown/sendcommand)
    - single process manages one-or-many servers
        - easier to run outside of managed ($$$) environments
        - only runs outside managed environments (for now?)
- server manager service manager (manman-host)
    - controls server manager service instances
    - exposes management API (worker/info/admin)

### not in this repo
UI - this will live in https://github.com/whale-net/orca project


## setup
this used to be like a little baby poetry project with complex imports but it's literally just 2 packages so just put it into a single module dangit

### install

This is a poetry project. install poetry https://python-poetry.org/
if you need a specific version of python that is different from your system, consider pyenv

If you use pyenv you may want to set this to make poetry use your pyenv local environment rather than creating a conflicting virtual environment
(you can also remove --local to make this default, but may need to restart your shell)
```
poetry config virtualenvs.prefer-active-python true --local
```

Otherwise, install
```
poetry install
```


