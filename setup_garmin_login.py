import garth
import os
import getpass
from dotenv import load_dotenv

load_dotenv()

def main():
    # Try getting creds from .env first
    email = os.getenv("GARMIN_EMAIL")
    password = os.getenv("GARMIN_PASSWORD")

    # If not in .env, ask user
    if not email:
        email = input("Enter Garmin email: ")
    else:
        print(f"Using email from .env: {email}")

    if not password:
        password = getpass.getpass("Enter Garmin password: ")
    else:
        print("Using password from .env")

    try:
        print(f"Attempting login for {email}...")
        garth.login(email, password)
        print("Login SUCCESS!")
        garth.save(".garth")
        print("Tokens saved.")

    except Exception as e:
        print("--- LOGIN FAILED ---")
        print(e)

if __name__ == "__main__":
    main()