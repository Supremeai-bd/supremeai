from infisical_client import ClientSettings, InfisicalClient, GetSecretOptions, AuthenticationOptions, UniversalAuthMethod
import sys

import os

def test_infisical():
    client_id = os.getenv('INFISICAL_CLIENT_ID', '')
    client_secret = os.getenv('INFISICAL_CLIENT_SECRET', '')
    project_id = os.getenv('INFISICAL_PROJECT_ID', '')
    
    if not client_id or not project_id:
        print("Error: INFISICAL_CLIENT_ID and INFISICAL_PROJECT_ID must be set in environment.")
        return

    print('Initializing client...')
    try:
        client = InfisicalClient(
            ClientSettings(
                auth=AuthenticationOptions(
                    universal_auth=UniversalAuthMethod(
                        client_id=client_id,
                        client_secret=client_secret,
                    )
                )
            )
        )
        print('Authenticated successfully.')
    except Exception as e:
        print(f'Authentication failed: {e}')
        return
        
    print('Trying to fetch DATABASE_CONFIG from prod environment...')
    try:
        secret = client.getSecret(
            options=GetSecretOptions(
                environment='prod',
                project_id=project_id,
                secret_name='DATABASE_CONFIG',
                path='/'
            )
        )
        print(f'Success! Fetched secret length: {len(secret.secret_value)}')
    except Exception as e:
        print(f'Failed to fetch from prod: {e}')
        
    print('Trying to fetch DATABASE_CONFIG from dev environment...')
    try:
        secret = client.getSecret(
            options=GetSecretOptions(
                environment='dev',
                project_id=project_id,
                secret_name='DATABASE_CONFIG',
                path='/'
            )
        )
        print(f'Success! Fetched secret length: {len(secret.secret_value)}')
    except Exception as e:
        print(f'Failed to fetch from dev: {e}')

if __name__ == '__main__':
    test_infisical()
