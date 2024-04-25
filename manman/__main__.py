import typer

app = typer.Typer()

@app.command()
def host(test: str):
    print(f"test {test}")

@app.command()
def worker(address: str):
    print(f"test {address}")

app()