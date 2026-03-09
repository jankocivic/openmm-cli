import typer

def minimization(
    name: str = typer.Argument(..., help="Name to greet"),
    count: int = typer.Option(1, "--count", help="Number of greetings"),
):
    """Perform energy minimization"""
    for _ in range(count):
        typer.echo(f"Hello {name}!")
