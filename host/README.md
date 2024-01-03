
# manman-host

poetry subproject
in general able to interact with it as you would any other poetry project

## installation
do not install locally

it will install locally to update the lock file, but it's not something you should do for other purposes

## running
do not run locally

it will reference old code
run from outer main project venv

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

