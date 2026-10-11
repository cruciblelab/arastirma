import sys

from . import __version__


def main() -> int:
    if any(a in ("--surum", "--version") for a in sys.argv[1:]):
        print(f"paket-guncelleyici {__version__}")
        return 0
    from .ui import run
    return run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
