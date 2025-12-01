from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import List
import shutil
import os
from pathlib import Path
import tempfile

from src.kakeibo.use_cases.process_file import ProcessFileUseCase
from src.kakeibo.domain.models import Transaction

app = FastAPI(title="Kakeibo API", description="API for processing bank statements")

class ProcessResponse(BaseModel):
    message: str
    processed_files: int

@app.get("/")
def read_root():
    return {"message": "Kakeibo API is running"}

@app.post("/process", response_model=ProcessResponse)
async def process_files(files: List[UploadFile] = File(...)):
    """
    Upload and process bank statement files.
    """
    use_case = ProcessFileUseCase()

    # Create a temporary directory for processing
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        input_dir = temp_path / "input"
        output_dir = temp_path / "output"
        input_dir.mkdir()

        saved_files = []
        for file in files:
            file_path = input_dir / file.filename
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            saved_files.append(file_path)

        # Process files
        success_count = 0
        for file_path in saved_files:
            if use_case.execute(file_path, output_dir):
                success_count += 1

        # In a real Vercel app, we might return the JSON data or save to Supabase here.
        # For now, we just acknowledge processing.

        return {
            "message": "Processing complete",
            "processed_files": success_count
        }

# Vercel entry point
# handler = app
