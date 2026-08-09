from __future__ import annotations

from pathlib import Path

import typer
import uvicorn
from loguru import logger
from rich.console import Console

from src.kakeibo.config import settings
from src.kakeibo.monthly_snapshot import SnapshotError, build_monthly_snapshot
from src.kakeibo.statement_types import StatementTypeError
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

    success_count = 0
    for file in files:
        source_type = use_case.infer_source_type(file.name)
        if source_type is None:
            logger.warning("Unsupported financial file")
            continue
        try:
            success_count += int(
                use_case.execute(
                    file,
                    output_dir,
                    source_type=source_type,
                )
            )
        except StatementTypeError:
            logger.warning("Unsupported statement contract")

    console.print(
        f"[bold green]Processed {success_count}/{len(files)} files.[/bold green]"
    )


@app.command("snapshot-month")
def snapshot_month(
    month: str = typer.Option(..., help="Target month in YYYY-MM"),
    input_paths: list[Path] = typer.Argument(..., help="Normalized private CSV files"),
    fx_source: str = typer.Option(..., help="FX source URL or source identifier"),
    fx_retrieved_at: str = typer.Option(..., help="FX retrieval timestamp in ISO-8601"),
    fx_rate: list[str] | None = typer.Option(
        None,
        "--fx-rate",
        help="Repeatable PAIR=RATE evidence, for example USDJPY=147.25",
    ),
    artifact_root: Path = typer.Option(Path("artifacts"), help="Private artifact root"),
) -> None:
    """Freeze hashes, FX provenance, and deterministic monthly totals."""
    rates: dict[str, str] = {}
    for item in fx_rate or []:
        pair, separator, rate = item.partition("=")
        if not separator or not pair.strip() or not rate.strip():
            logger.error("Invalid FX rate evidence")
            raise typer.Exit(code=1)
        rates[pair.strip()] = rate.strip()

    try:
        result = build_monthly_snapshot(
            month=month,
            input_paths=input_paths,
            artifact_root=artifact_root,
            fx_source=fx_source,
            fx_retrieved_at=fx_retrieved_at,
            fx_rates=rates,
        )
    except (OSError, SnapshotError):
        logger.error("Monthly snapshot failed")
        raise typer.Exit(code=1) from None
    console.print(f"snapshot_sha256={result['metadata_sha256']}")


@app.command()
def review(port: int = typer.Option(8765, min=1024, max=65535)) -> None:
    """Run the local-only Import Review UI on the loopback interface."""
    console.print(f"Import Review: http://127.0.0.1:{port}")
    uvicorn.run(
        "src.kakeibo.import_review:app",
        host="127.0.0.1",
        port=port,
        access_log=False,
    )


@app.command()
def config() -> None:
    """Show only the non-sensitive configuration snapshot."""
    console.print(settings.public_snapshot())


if __name__ == "__main__":
    app()
