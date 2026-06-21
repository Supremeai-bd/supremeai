import os
import sys
import google.generativeai as genai

def run_zero_cost_audit():
    api_key = os.environ.get("GEMINI_API_KEY")
    diff_content = os.environ.get("PR_DIFF_CONTENT")

    if not api_key or not diff_content:
        print("No API Key or empty diff. Skipping AI review.")
        sys.exit(0)

    # জিরো-কস্ট এবং ফাস্ট স্ক্যানের জন্য 'Flash' মডেল ব্যবহার করা হচ্ছে
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')

    print("Analyzing incremental code changes...")
    
    prompt = f"""You are an elite DevSecOps AI. Review ONLY the following code changes (git diff) for:
    1. Critical security bugs (hardcoded secrets, injections).
    2. Severe performance bottlenecks.
    3. Logical errors in the new changes.
    
    If the code looks good, strictly reply with "✅ No critical issues found in this diff."
    Otherwise, provide a short, bulleted list of the exact issues.
    
    Code Diff:
    ```diff
    {diff_content}
    ```
    """

    try:
        response = model.generate_content(prompt)
        report = response.text
        
        with open("pr_review_report.md", "w", encoding="utf-8") as f:
            f.write(report)
            
        print("AI Review completed.")
            
    except Exception as e:
        print(f"AI Review Failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass
    run_zero_cost_audit()
