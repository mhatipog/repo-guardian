"""Run `python -m repoguardian` from source or installed package."""
from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
