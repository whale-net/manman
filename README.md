# manman
([cs2/game]server)man(ager)man(ager)


## about

successor of https://github.com/whale-net/cs-server-runner

more cloud friendly

hopefully better patterns

easier deployment (maybe?)

fun fact: according to https://en.wiktionary.org/wiki/manman, manman is mother in haitian creole, and is the act of observing in tagalog
this project is the mother and observer to all the little workers

architecture
```mermaid
---
config:
  theme: redux
---
graph TD
    subgraph "Worker Service Layer"
        worker-svc["worker service"]
        servers["server"]@{ shape: procs}
        server-subproc["steamcmd & ./gameserver"]@{ shape: subproc }
    end

    subgraph "API Layer"
        http-ingress[/"external-ingress"\]
        experience-api["experience-api"]
        worker-dal-api["worker-dal-api"]
        status-api["status-api"]
        status-processor["status-processor"]@{ shape: proc }
    end

    subgraph "Data Layer"
        database["manman"]@{ shape: db}
    end

    subgraph "Messaging Layer"
        rmq{{"rabbitmq"}}
    end

    subgraph "External Integrations"
        slack-bot["slack-bot (fcm)"]
    end

    %% Core Worker Flow
    worker-svc --> servers --> server-subproc

    %% HTTP Ingress and API interactions
    http-ingress --> experience-api
    http-ingress -- exposed for now --> status-api
    http-ingress -- exposed for now --> worker-dal-api

    %% Service to Ingress Communication
    worker-svc --> http-ingress
    servers --> http-ingress

    %% API to Database Communication
    experience-api --> database
    worker-dal-api --> database
    status-processor --> database
    status-api --> database

    %% RabbitMQ Interactions
    rmq <--> worker-svc
    rmq <--> servers
    rmq <--> experience-api
    rmq <--> status-processor

    %% Slack Bot Interactions
    slack-bot --> experience-api
    slack-bot --> status-api

    %% Comment
    http-ingress-comment["NOTE: worker-svc/servers<br>will only use the worker-dal-api<br>via the http-ingress"]@{ shape: comment }
    http-ingress-comment -.- http-ingress
```

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
~~UI - this will live in https://github.com/whale-net/orca project~~


going to try and expose via slack instead. Don't want to have to maintain a javascript ui.



## setup

this is uv project. install using the following commands:
```bash
uv venv
source .venv/bin/activate
uv sync
```


### running locally

Put env vars into `.env` file.
This is not required for running tilt, as tilt will autoload them.
These can be exported using the following command:
```bash
export $(cat .env | xargs)
```

Host can be started with Tilt.
Service updates can be paused in tilt if you aren't modifying them.
This will reduce the number of restarts and speed up development.
```bash
tilt up
```

or done manually.
I do not recommend starting outside of tilt, although it can be done.
If you do start outside tilt, make sure all env vars are set to tilt services.
The manual approach is handy for creating and running migrations.

service commands:
```bash
uv run host start-experience-api
```
```bash
uv run host start-worker-dal-api
```
```bash
uv run host start-status-api
```
```bash
uv run host start-status-processor
```

migration commands:
```bash
uv run host run-migration
```
```bash
uv run host create-migration
```
```bash
uv run host run-downgrade <hash>
```

start the worker
```bash
uv run worker start
```
