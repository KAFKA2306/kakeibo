from pathlib import Path

from loguru import logger

from src.kakeibo.adapters.parsers.generic_csv import GenericCsvParser
from src.kakeibo.adapters.parsers.sony import SonyBankParser
from src.kakeibo.config import settings
from src.kakeibo.domain.cleaning import CleaningPipeline


class ProcessFileUseCase:
    def __init__(self):
        self.cleaning_pipeline = CleaningPipeline()
        self.parsers = {
            "sony": SonyBankParser(),
            "generic": GenericCsvParser(),
            # 他のパーサーもここに追加
        }

    def execute(self, file_path: Path, output_dir: Path | None = None) -> bool:
        if output_dir is None:
            output_dir = Path(settings.output_dir)

        logger.info(f"Processing file: {file_path}")

        # 1. Identify File Type (簡易実装: ファイル名マッチング)
        file_type = self._identify_file_type(file_path.name)
        if not file_type:
            logger.warning(f"Unknown file type: {file_path.name}")
            return False

        parser = self.parsers.get(file_type, self.parsers["generic"])
        encoding = settings.default_encodings.get(file_type, "utf-8")

        try:
            # 2. Parse
            raw_df = parser.parse(file_path, encoding=encoding)

            # 3. Clean
            clean_df = self.cleaning_pipeline.process(raw_df, source=file_type)

            # 4. Save
            output_path = output_dir / f"{file_path.stem}.csv"
            output_dir.mkdir(parents=True, exist_ok=True)
            clean_df.write_csv(output_path)

            logger.success(f"Successfully processed: {output_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to process {file_path}: {e}")
            # リトライロジック (エンコーディング変更など) はここに実装可能
            return False

    def _identify_file_type(self, filename: str) -> str | None:
        import re

        for type_name, pattern in settings.file_patterns.items():
            if re.search(pattern, filename, re.IGNORECASE):
                return type_name
        return None
