import argparse
import asyncio

from api.db import db_client
from api.porter.mock_leads import MOCK_LEAD_SOURCE, load_mock_porter_leads


async def _run(replace: bool) -> int:
    async with db_client.async_session() as session:
        leads = await load_mock_porter_leads(session, replace=replace)
        await session.commit()
        return len(leads)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load clearly fake Porter mock leads for local validation."
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help=f"Delete existing {MOCK_LEAD_SOURCE} leads before loading fixtures.",
    )
    args = parser.parse_args()

    count = asyncio.run(_run(replace=args.replace))
    print(f"Loaded {count} Porter mock leads from {MOCK_LEAD_SOURCE}.")


if __name__ == "__main__":
    main()
