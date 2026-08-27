with open('backend/requirements.txt', 'a') as f:
    f.write('\npython-jose[cryptography]==3.4.0 ; python_version >= "3.11" and python_version < "4.0"\n')
