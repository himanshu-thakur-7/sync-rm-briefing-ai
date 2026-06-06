"""
Trigger a test briefing call through the local backend.

Usage:
  python scripts/test_call.py --client "Rahul Mehta" --phone "+919876543210"
"""
import argparse
import asyncio

import httpx


async def main() -> None:
    """Find a client by name and trigger a SYNC call."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", required=True)
    parser.add_argument("--phone", required=True)
    parser.add_argument("--rm-name", default="Himanshu")
    parser.add_argument("--backend-url", default="http://localhost:8000")
    args = parser.parse_args()

    async with httpx.AsyncClient(timeout=30) as client:
        search = await client.get(
            f"{args.backend_url}/api/v1/clients/search",
            params={"name": args.client},
        )
        search.raise_for_status()
        matches = search.json()
        if not matches:
            raise SystemExit(f"No client matched {args.client!r}")

        selected = matches[0]
        response = await client.post(
            f"{args.backend_url}/api/v1/calls/sync-now",
            json={
                "client_id": selected["client_id"],
                "rm_phone": args.phone,
                "rm_name": args.rm_name,
            },
        )
        response.raise_for_status()
        data = response.json()

    print(f"Client: {selected['name']}")
    print(f"Call ID: {data['call_id']}")
    print(f"Status: {data['status']}")
    print(f"Preview: {data['briefing_preview']}")


if __name__ == "__main__":
    asyncio.run(main())
