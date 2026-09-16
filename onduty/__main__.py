"""`python -m onduty ...` 入口,全部命令逻辑见 onduty/cli.py。"""
import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
