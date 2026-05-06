"""Typer CLI entry point. Commands populated by Plan 05."""
import typer

app = typer.Typer(name="hsb", help="HSBTech AI Engineering Workflow CLI")


@app.callback()
def main() -> None:
    """HSBTech AI Engineering Workflow CLI."""


if __name__ == "__main__":
    app()
