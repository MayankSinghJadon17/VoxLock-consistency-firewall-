from __future__ import annotations

import asyncio

from .demo import main as demo_main


def main() -> None:
    asyncio.run(demo_main())


if __name__ == "__main__":
    main()
