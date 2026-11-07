import os
import sys
import dotenv

def main():
    dotenv.load_dotenv(r"f:\supremeai\.env")
    
    # Import check_secrets function logic from script
    from scripts.ci.check_required_secrets import check_secrets
    check_secrets()

if __name__ == "__main__":
    main()
