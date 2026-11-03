"""
Print fresh values for the two required secrets, ready to paste into .env.

    python -m app.keys            # print to stdout
    python -m app.keys >> ../.env # append to the root .env
"""
import secrets

from cryptography.fernet import Fernet


def main() -> None:
    print(f"APP_SECRET_KEY={secrets.token_urlsafe(48)}")
    print(f"APP_ENCRYPTION_KEY={Fernet.generate_key().decode()}")


if __name__ == "__main__":
    main()
