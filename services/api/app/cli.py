"""Operator commands.

    python -m app.cli create-platform-admin --email you@example.com --name "Your Name"
"""

import argparse
import asyncio
import getpass
import os
import sys

from sqlalchemy.exc import IntegrityError

import app.models  # noqa: F401 - registers every table before any query
from app.core.db import DbContext, open_session
from app.core.security import MIN_PASSWORD_LENGTH, hash_password
from app.modules.audit import service as audit
from app.modules.users.models import User


async def create_platform_admin(email: str, name: str, password: str) -> None:
    async with open_session(DbContext.system()) as db:
        user = User(email=email.lower(), full_name=name, password_hash=hash_password(password),
                    is_platform_admin=True, status="active")
        db.add(user)
        try:
            await db.flush()
        except IntegrityError:
            sys.exit(f"A user with email {email} already exists.")
        await audit.record(db, company_id=None, action="platform_admin.created",
                           entity_type="user", entity_id=user.id, payload={"email": user.email})
        await db.commit()
    print(f"Platform Admin {email} created. Sign in to set up your second factor.")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create-platform-admin")
    create.add_argument("--email", required=True)
    create.add_argument("--name", required=True)
    args = parser.parse_args()

    if args.command == "create-platform-admin":
        password = os.environ.get("PF_ADMIN_PASSWORD") or getpass.getpass("Password: ")
        if len(password) < MIN_PASSWORD_LENGTH:
            sys.exit(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
        asyncio.run(create_platform_admin(args.email, args.name, password))


if __name__ == "__main__":
    main()
