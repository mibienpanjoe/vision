"""Machine-local administration; never expose this as a registration route."""
import argparse
import getpass
import sys

from app.core.passwords import hash_password
from app.db.session import configured_engine
from app.models.access import Principal
from app.schemas.access import LoginRequest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def main() -> int:
    parser = argparse.ArgumentParser(description="Vision local account administration")
    parser.add_argument("command", choices=["create-user"])
    parser.add_argument("username")
    parser.add_argument("--password-stdin", action="store_true", help="Read passphrase from stdin without echo")
    args = parser.parse_args()
    password = sys.stdin.readline(514).rstrip("\r\n") if args.password_stdin else getpass.getpass("Passphrase: ")
    try:
        body = LoginRequest(username=args.username, password=password)
    except ValidationError:
        print("Invalid username or passphrase.", file=sys.stderr)
        return 1
    engine = configured_engine()
    if engine is None:
        print("Configure DATABASE_URL first.", file=sys.stderr)
        return 1
    try:
        with Session(engine) as db:
            principal = Principal(username=body.username, password_hash=hash_password(body.password))
            db.add(principal)
            db.commit()
            print(f"Created local account {body.username}.")
    except IntegrityError:
        print("Local account already exists.", file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
