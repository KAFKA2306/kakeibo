# Kakeibo: Modern Data Processing System

## Overview

This is a modern, clean architecture-based system for processing and analyzing bank transaction data. It is built with Python, using `Polars` for high-performance data manipulation and `Pydantic` for robust data validation.

## Features

- **Clean Architecture**: Separation of concerns (Domain, Ports, Adapters, Use Cases).
- **High Performance**: Uses `Polars` for fast data processing.
- **Type Safety**: Fully typed codebase with `Pydantic` models.
- **Flexible Pipeline**: Extensible data cleaning pipeline.
- **CLI**: Modern command-line interface powered by `Typer`.
- **Cloud Ready**: Includes `FastAPI` entry point and `Supabase` integration structure for Vercel deployment.

## Installation

This project uses `poetry` for dependency management.

```bash
poetry install
```

## Usage

### Process Files (CLI)

To process bank statement files:

```bash
python src/kakeibo/cli.py process /path/to/input_dir --output-dir /path/to/output_dir
```

Or a single file:

```bash
python src/kakeibo/cli.py process /path/to/file.csv
```

### API Server

To run the API server (compatible with Vercel):

```bash
uvicorn src.kakeibo.api:app --reload
```

### Configuration

The system uses `pydantic-settings`. You can override settings via environment variables (prefix `KAKEIBO_`).
For Supabase integration, set:
- `SUPABASE_URL`
- `SUPABASE_KEY`

To see current configuration:

```bash
python src/kakeibo/cli.py config
```

## Project Structure

```
src/
  kakeibo/
    domain/          # Domain models and business rules
    ports/           # Interfaces (Ports)
    adapters/        # Implementations (Adapters: Parsers, Repositories)
    use_cases/       # Application Logic
    cli.py           # Command Line Interface
    api.py           # FastAPI Application (for Vercel)
```
