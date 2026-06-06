"""
Preview the seeded SYNC demo data.

The backend uses in-memory demo data at startup, so restarting FastAPI resets
the demo. This script prints the current seed roster for quick verification.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "artifacts" / "sync-backend"
sys.path.insert(0, str(BACKEND))

import database  # noqa: E402


def main() -> None:
    """Print the seeded mock CRM clients."""
    for client in database.CLIENTS.values():
        profile = client.profile
        print(f"{profile.client_id}: {profile.name} | {profile.company} | risk={client.risk.score}")


if __name__ == "__main__":
    main()
