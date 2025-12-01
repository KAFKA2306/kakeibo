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

This project uses `uv` for dependency management.

```bash
task install
```

## Usage

This project uses `Taskfile` to manage common tasks.

### Process Files (CLI)

To process bank statement files:

```bash
task cli -- process /path/to/input_dir --output-dir /path/to/output_dir
```

### API Server

To run the API server (compatible with Vercel):

```bash
task dev
```

### Development

Common development tasks:

```bash
task test       # Run tests
task lint       # Run linters
task format     # Format code
task typecheck  # Run static type checks
```

### Configuration

The system uses `pydantic-settings`. You can override settings via environment variables (prefix `KAKEIBO_`).
For Supabase integration, set:
- `SUPABASE_URL`
- `SUPABASE_KEY`

To see current configuration:

```bash
task cli -- config
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
