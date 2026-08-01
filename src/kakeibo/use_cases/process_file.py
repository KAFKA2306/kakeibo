import re
from pathlib import Path

from loguru import logger

from src.kakeibo.adapters.parsers.generic_csv import GenericCsvParser
from src.kakeibo.adapters.parsers.sony import SonyBankParser
from src.kakeibo.config import settings
from src.kakeibo.domain.cleaning import CleaningPipeline
from src.kakeibo.security import opaque_file_id, private_output_name


class ProcessFileUseCase:
    def __init__(self) -> None:
        self.cleaning_pipeline = CleaningPipeline()
        self.parsers = {
            "sony": SonyBankParser(),
            "generic": GenericCsvParser(),
        }

    def execute(self, file_path: Path, output_dir: Path | None = None) -> bool:
        if output_dir is None:
            output_dir = settings.output_dir

        file_id = opaque_file_id(file_path)
        logger.info("Processing financial file id={}", file_id)

        file_type = self._identify_file_type(file_path.name)
        if not file_type:
            logger.warning("Unsupported financial file id={}", file_id)
            return False

        parser = self.parsers.get(file_type, self.parsers["generic"])
        encoding = settings.default_encodings.get(file_type, "utf-8")

        try:
            raw_df = parser.parse(file_path, encoding=encoding)
            clean_df = self.cleaning_pipeline.process(raw_df, source=file_type)

            output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            output_path = output_dir / private_output_name()
            clean_df.write_csv(output_path)

            logger.success("Processed financial file id={}", file_id)
            return True
        except Exception as exc:
            logger.error(
                "Financial file processing failed id={} error_type={}",
                file_id,
                type(exc).__name__,
            )
            return False

    def _identify_file_type(self, filename: str) -> str | None:
        for type_name, pattern in settings.file_patterns.items():
            if re.search(pattern, filename, re.IGNORECASE):
                return type_name
        return None
