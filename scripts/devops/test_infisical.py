from infisical_client import ClientSettings, InfisicalClient, GetSecretOptions, AuthenticationOptions, UniversalAuthMethod
import sys

import os

def test_infisical():
    client_id = os.getenv('INFISICAL_CLIENT_ID', '9f2363cf-3cec-43f6-b155-a8625de19250')
    client_secret = os.getenv('INFISICAL_CLIENT_SECRET', '')
    project_id = os.getenv('INFISICAL_PROJECT_ID', '92aa20c4-aef5-4e33-82bd-efb06058aaf0')
    
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
        sys.exit(1)
        
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
        print(f'Success! Secret value: {secret.secret_value}')
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
        print(f'Success! Secret value: {secret.secret_value}')
    except Exception as e:
        print(f'Failed to fetch from dev: {e}')

if __name__ == '__main__':
    test_infisical()
