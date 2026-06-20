import os
import sys
import subprocess
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted, GoogleAPICallError

def main():
    # Collect API keys
    api_keys = []
    
    # 1. Check GEMINI_API_KEYS (comma-separated)
    if "GEMINI_API_KEYS" in os.environ:
        api_keys.extend([k.strip() for k in os.environ["GEMINI_API_KEYS"].split(",") if k.strip()])
    
    # 2. Check individual GEMINI_API_KEY_* variables
    for k, v in os.environ.items():
        if k.startswith("GEMINI_API_KEY") and k != "GEMINI_API_KEYS" and v.strip():
            api_keys.append(v.strip())
            
    # 3. Check fallback GEMINI_API_KEY
    if "GEMINI_API_KEY" in os.environ and os.environ["GEMINI_API_KEY"].strip():
        api_keys.append(os.environ["GEMINI_API_KEY"].strip())
        
    # Remove duplicates while preserving order
    api_keys = list(dict.fromkeys(api_keys))
    
    if not api_keys:
        print("Error: No Gemini API Key found. Please set GEMINI_API_KEY or GEMINI_API_KEYS in secrets.")
        sys.exit(1)
        
    print(f"Found {len(api_keys)} Gemini API Key(s) to use.")

    # Extract git diff
    try:
        # Get diff between current commit and parent
        diff_cmd = "git diff HEAD~1 HEAD"
        diff_output = subprocess.check_output(diff_cmd.split()).decode("utf-8")
    except Exception as e:
        # If HEAD~1 doesn't exist (first commit/shallow clone), try alternative
        try:
            diff_cmd = "git diff-tree --no-commit-id --cc HEAD"
            diff_output = subprocess.check_output(diff_cmd.split()).decode("utf-8")
        except Exception as ex:
            print(f"Error getting diff: {ex}")
            sys.exit(1)

    if not diff_output.strip():
        print("No changes found to review.")
        sys.exit(0)

    prompt = f"""
You are a senior software engineer. Review the following code changes. 
Point out any bugs, security vulnerabilities, or performance issues. 
Keep your feedback concise and actionable.

Additionally, provide some 'Pro Tips' on how these changes or architectural adjustments can help SupremeAI become the best self-learning AI model (e.g., in terms of efficiency, scalability, and code cleanliness).

Code changes:
{diff_output}
"""

    response_text = None
    for i, key in enumerate(api_keys):
        try:
            print(f"Attempting review with Key {i+1}...")
            genai.configure(api_key=key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(prompt)
            response_text = response.text
            print(f"Success with Key {i+1}!")
            break
        except ResourceExhausted:
            print(f"Key {i+1} rate limit exhausted. Trying next key...")
        except GoogleAPICallError as e:
            print(f"Key {i+1} failed with API error: {e}. Trying next key...")
        except Exception as e:
            print(f"Key {i+1} failed: {e}. Trying next key...")

    if not response_text:
        print("Warning: All Gemini API keys failed or rate limited. Skipping code review without failing the build.")
        sys.exit(0)

    print("\n--- Gemini Code Review ---\n")
    print(response_text)

if __name__ == "__main__":
    main()
