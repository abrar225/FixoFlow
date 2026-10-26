"""OS entry point. Cocoa is never imported by Windows or Linux."""
import sys


def main(argv=None):
    if sys.platform == 'darwin':
        from fixoflow.app import main as run
    else:
        from fixoflow.desktop_app import main as run
    return run(argv)


if __name__ == '__main__':
    main()
