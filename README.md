# manman
([cs2/game]server)man(ager)man(ager)


## setup
both projects exist in this repo as separate poetry projects managed via another poetry 'virtual-project'

this enables a single repo to host two projects and share tooling (CI/CD)
but also introduces some development complexity. however the tradeoff has been deemed worth it for this project


### install

For local development installing all projects is the easiest way to develop and not an issue
The virutal project is setup to install all dev dependencies
```
poetry install --no-root
```
NOTE: the no-root option prevents the project from attempting to install a `manman` package that does not exist

install a single project
```
poetry install --no-root --only {host | worker}
```

### adding dependencies
see individual project README for how to add dependencies


### running
install individual project
```
cd <project>
poetry install
```

run code
```
poetry run python .
```

eventually will have docker image


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

