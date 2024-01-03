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
both projects exist in this repo as separate poetry projects managed via another poetry 'virtual-project'

this enables a single repo to host two projects and share tooling (CI/CD) while still allowing separate artifact deployment


### install

This is a poetry project. install poetry https://python-poetry.org/
if you need a specific version of python that is different from your system, consider pyenv

For local development installing all projects is the easiest way to develop
```
poetry install --no-root
```
NOTE: the no-root option prevents the project from attempting to install a `manman` package that does not exist


install a single project
useful for deployment, and could be useful for local dev, but installing all is still recommended for simplicity
```
poetry install --no-root --only {host | worker}
```

run projects
```
poetry run python -m manman.{host | worker}
```


### adding dependencies
see individual project README for how to add dependencies
it is very easy, but I am keeping track of any bodges per-project

### running
install individual project
```
poetry install --no-root --only host
```

run code
```
poetry run python -m manman.host
```

eventually will have docker image for each project


### WARNING
don't ever run from within the subproject (e.g. `host`). 
always run from the outer virtual project, otherwise old dependencies can be referenced and cause very frustrating issues
