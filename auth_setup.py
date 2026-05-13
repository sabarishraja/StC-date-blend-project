import os
from google_auth_oauthlib.flow import InstalledAppFlow

# Define the scopes we need for GA4 and Google Search Console
SCOPES = [
    'https://www.googleapis.com/auth/analytics.readonly',
    'https://www.googleapis.com/auth/webmasters.readonly'
]

def main():
    print("Starting authentication flow...")
    print("A browser window should open asking you to log in to your Google Account.")
    
    # Create the flow using the client secrets file from the Google Cloud Console.
    flow = InstalledAppFlow.from_client_secrets_file(
        'oauth-credentials.json',
        scopes=SCOPES
    )
    
    # Run the local server to handle the OAuth2 redirect
    creds = flow.run_local_server(port=0)
    
    # Save the credentials for the next run
    with open('token.json', 'w') as token:
        token.write(creds.to_json())
        
    print("\n✅ Authentication successful!")
    print("The credentials have been saved to 'token.json'.")
    print("You can now safely delete or ignore 'ga4-credentials.json'.")

if __name__ == '__main__':
    main()
