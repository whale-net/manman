
# manman-worker

poetry subproject
in general able to interact with it as you would any other poetry project

## why this directory layout?
each sub-project is treated as its own submodule in a shared `manman` project. 
you can explore this in the `.venv/lib/manman` folder in the root of this repo after installing

so although this isn't exactly convenient, it is functional

## installation
although you shouldn't need this during development, install locally with

```
poetry install
```

if need develop dependencies (installed by default when installing from virtual project), use the extras develop group
```
poetry install --extras develop
```

execute locally with 
```
poetry run python -m manman.worker
```
this will run the project in the context of the project's poetry virtual environment with all of the project's dependencies installed

note: if dev dependencies are required to run the production artifact, it will throw a dependency error

## adding dependencies
there are two ways to add dependencies

### production dependencies
dependencies that **are** included in the production artifact

add them as you would normally
```
poetry add <package>
```

### dev dependencies
dependencies that **are not** included in the production artifact

add the dependency to poetry as optional, so that it is not installed by default
although not the traditional way of handling dev dependencies, this works just as well
```
poetry add <package> --optional
```

then manually modify the pyproject.toml file `[tool.poetry.extras]` `develop` to include the new dependency
```
[tool.poetry.extras]
develop = [..., "<package>"]
```

