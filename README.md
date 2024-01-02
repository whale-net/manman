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
        - easier to run outside managed ($$$) environments
        - only runs outside managed environments (for now?)
- server manager service manager (manman-host)
    - controls server manager service instances
    - exposes management API (worker/info/admin)

### not in this repo
UI - this will live in https://github.com/whale-net/orca project

