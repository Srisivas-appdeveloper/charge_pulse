"""Seeding superadmin CLI script."""
from __future__ import annotations

import argparse
import asyncio
import getpass
import os
from pathlib import Path

import asyncpg
import bcrypt
from dotenv import load_dotenv


def hash_password(plain: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", default="Super Admin")
    args = parser.parse_args()

    password = getpass.getpass("Enter password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Error: Passwords do not match.")
        return

    # Load environment variables from backend/.env
    env_path = Path(__file__).parent.parent / "backend" / ".env"
    load_dotenv(dotenv_path=env_path)

    host = os.getenv("POSTGRES_HOST", "localhost")
    port = int(os.getenv("POSTGRES_PORT", "5433"))
    db = os.getenv("POSTGRES_DB", "chargepulse")
    user = os.getenv("POSTGRES_USER", "chargepulse")
    pw = os.getenv("POSTGRES_PASSWORD", "change_me_in_production")

    print(f"Connecting to database {db} on {host}:{port} as user {user}...")
    conn = await asyncpg.connect(host=host, port=port, database=db, user=user, password=pw)
    try:
        # Check existing superadmins
        existing = await conn.fetchrow("SELECT id FROM superadmins WHERE email = $1", args.email)
        if existing:
            print(f"Error: Superadmin with email {args.email} already exists.")
            return

        # Check existing users
        existing_u = await conn.fetchrow("SELECT id FROM users WHERE email = $1", args.email)
        if existing_u:
            print(f"Error: User with email {args.email} already exists in users table.")
            return

        hashed = hash_password(password)
        await conn.execute(
            "INSERT INTO superadmins (email, password_hash, full_name) VALUES ($1, $2, $3)",
            args.email,
            hashed,
            args.name,
        )
        print(f"Superadmin {args.email} successfully created!")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
