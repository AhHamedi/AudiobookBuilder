# Contributing

Thanks for helping improve AudiobookBuilder.

## Development setup

1. Install Python 3.9 or newer and FFmpeg: `brew install ffmpeg`.
2. Create a virtual environment: `python3 -m venv .venv`.
3. Activate it: `source .venv/bin/activate`.
4. Install the project: `python -m pip install -e '.[dev]'`.

Run the quality checks before opening a pull request:

```bash
ruff check .
ruff format --check .
pytest
python -m build
python -m twine check dist/*
```

Keep changes focused, add tests for behavior changes, and update the README when the public CLI changes.
