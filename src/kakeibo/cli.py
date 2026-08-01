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
    output_dir: Path | None = typer.Option(None, help="Private output directory"),
) -> None:
    """Process bank statement files without printing paths or filenames."""
    use_case = ProcessFileUseCase()

    if input_path.is_file():
        files = [input_path]
    elif input_path.is_dir():
        files = [file for file in input_path.iterdir() if file.is_file()]
    else:
        logger.error("Invalid input path")
        raise typer.Exit(code=1)

    success_count = sum(use_case.execute(file, output_dir) for file in files)
    console.print(
        f"[bold green]Processed {success_count}/{len(files)} files.[/bold green]"
    )


@app.command()
def config() -> None:
    """Show only the non-sensitive configuration snapshot."""
    console.print(settings.public_snapshot())


if __name__ == "__main__":
    app()
