import argparse
import asyncio

from api.db import db_client
from api.porter.knowledge_base import PORTER_KB_VERSION, seed_porter_knowledge_base


async def _run(replace: bool, version: str) -> None:
    async with db_client.async_session() as session:
        chunks = await seed_porter_knowledge_base(
            session,
            version=version,
            replace=replace,
        )
        await session.commit()
        print(f"Loaded {len(chunks)} Porter knowledge chunks for {version}.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Load Porter approved KB chunks.")
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--version", default=PORTER_KB_VERSION)
    args = parser.parse_args()

    asyncio.run(_run(replace=args.replace, version=args.version))


if __name__ == "__main__":
    main()
