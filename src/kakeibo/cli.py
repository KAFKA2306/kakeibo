from pathlib import Path

import typer
from loguru import logger
from rich.console import Console

from src.kakeibo.config import settings
from src.kakeibo.use_cases.process_file import ProcessFileUseCase

app = typer.Typer()
console = Console()


@app.command()
def process(
    input_path: Path = typer.Argument(..., help="Input file or directory"),
    output_dir: Path | None = typer.Option(None, help="Output directory"),
):
    """
    Process bank statement files.
    """
    use_case = ProcessFileUseCase()

    if input_path.is_file():
        files = [input_path]
    elif input_path.is_dir():
        files = [f for f in input_path.iterdir() if f.is_file()]
    else:
        logger.error(f"Invalid input path: {input_path}")
        raise typer.Exit(code=1)

    success_count = 0
    for file in files:
        if use_case.execute(file, output_dir):
            success_count += 1

    console.print(
        f"[bold green]Processed {success_count}/{len(files)} files.[/bold green]"
    )


@app.command()
def config():
    """Show current configuration."""
    console.print(settings.model_dump())


if __name__ == "__main__":
    app()
