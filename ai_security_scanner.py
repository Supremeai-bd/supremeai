import os
import sys
import google.generativeai as genai

CONTEXT_FILE = "supremeai_god_context.xml"

def run_security_audit():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not found.")
        sys.exit(1)

    genai.configure(api_key=api_key)
    
    # 1.5 Pro মডেল ব্যবহার করছি কারণ এর 2M কনটেক্সট উইন্ডো আছে
    model = genai.GenerativeModel('gemini-1.5-pro')

    if not os.path.exists(CONTEXT_FILE):
        print(f"Error: {CONTEXT_FILE} not found. Run context builder first.")
        sys.exit(1)

    print("Reading project context...")
    with open(CONTEXT_FILE, 'r', encoding='utf-8') as f:
        codebase_context = f.read()

    print("Sending codebase to Gemini for Security Audit. This may take a few minutes...")
    
    # DevSecOps প্রম্পট
    prompt = f"""You are an elite DevSecOps AI Engineer. Review the following codebase for critical security vulnerabilities.
    Focus on:
    1. Hardcoded secrets or API keys.
    2. SQL/NoSQL Injection vulnerabilities.
    3. Authentication/Authorization bypass flaws.
    4. XSS or CSRF in frontend components.
    
    Output the result in strict Markdown format. If no vulnerabilities are found, output a success message.
    
    Codebase XML:
    {codebase_context}
    """

    try:
        response = model.generate_content(prompt)
        report = response.text
        
        # রিপোর্টটি কনসোলে প্রিন্ট করা
        print("\n" + "="*50)
        print("🚨 SUPREMEAI SECURITY AUDIT REPORT 🚨")
        print("="*50 + "\n")
        print(report)
        
        # GitHub Step Summary-তে দেখানোর জন্য একটি ফাইলে সেভ করা
        with open("security_report.md", "w", encoding="utf-8") as f:
            f.write(report)
            
    except Exception as e:
        print(f"API Request Failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass
    run_security_audit()
