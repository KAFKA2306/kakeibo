from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from src.kakeibo.config import settings
from src.kakeibo.domain.cleaning import CleaningPipeline
from src.kakeibo.ports.parser import ParserPort
from src.kakeibo.security import opaque_file_id, private_output_name
from src.kakeibo.statement_types import (
    StatementTypeError,
    build_parser_registry,
    infer_statement_type,
    statement_spec,
)


@dataclass(frozen=True)
class ProcessingPlan:
    source_type: str
    suffix: str
    encoding: str
    parser: ParserPort


class ProcessFileUseCase:
    def __init__(self) -> None:
        self.cleaning_pipeline = CleaningPipeline()
        self.parsers = build_parser_registry()

    def processing_plan(self, source_type: str, suffix: str) -> ProcessingPlan:
        spec = statement_spec(source_type, suffix)
        parser = self.parsers.get(spec.name)
        if parser is None:
            raise StatementTypeError("statement type has no registered parser")
        return ProcessingPlan(
            source_type=spec.name,
            suffix=suffix.lower(),
            encoding=spec.encoding,
            parser=parser,
        )

    def infer_source_type(self, filename: str) -> str | None:
        return infer_statement_type(filename)

    def execute(
        self,
        file_path: Path,
        output_dir: Path | None = None,
        *,
        source_type: str | None = None,
    ) -> bool:
        if output_dir is None:
            output_dir = settings.output_dir

        file_id = opaque_file_id(file_path)
        selected_type = source_type or self.infer_source_type(file_path.name)
        if selected_type is None:
            logger.warning("Unsupported financial file id={}", file_id)
            return False

        plan = self.processing_plan(selected_type, file_path.suffix)
        logger.info(
            "Processing financial file id={} source_type={}",
            file_id,
            plan.source_type,
        )

        try:
            raw_df = plan.parser.parse(file_path, encoding=plan.encoding)
            clean_df = self.cleaning_pipeline.process(
                raw_df,
                source=plan.source_type,
            )

            output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            output_path = output_dir / private_output_name()
            clean_df.write_csv(output_path)

            logger.success(
                "Processed financial file id={} source_type={}",
                file_id,
                plan.source_type,
            )
            return True
        except StatementTypeError:
            raise
        except Exception as exc:
            logger.error(
                "Financial file processing failed id={} source_type={} error_type={}",
                file_id,
                plan.source_type,
                type(exc).__name__,
            )
            return False
