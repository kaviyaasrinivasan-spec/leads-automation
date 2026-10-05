import os
from google_auth_oauthlib.flow import InstalledAppFlow

# Google Ads API scope
SCOPES = ["https://www.googleapis.com/auth/adwords"]
CLIENT_SECRETS_PATH = "client_secret.json"

def main():
    if not os.path.exists(CLIENT_SECRETS_PATH):
        print(f"Error: {CLIENT_SECRETS_PATH} not found.")
        return

    flow = InstalledAppFlow.from_client_secrets_file(
        CLIENT_SECRETS_PATH, SCOPES
    )
    
    # Run local server to authenticate
    print("Opening browser for authentication...")
    credentials = flow.run_local_server(port=0)

    print("\n" + "=" * 50)
    print("SUCCESS! Your Refresh Token is below:")
    print("=" * 50)
    print(credentials.refresh_token)
    print("=" * 50)
    print("\nPlease copy the Refresh Token above and send it here.")

if __name__ == "__main__":
    main()
