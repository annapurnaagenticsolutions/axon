"""Allow `python -m axon ...` during local development."""

from axon.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
