import os
import sys
import subprocess
import google.generativeai as genai

def analyze_docker_bloat():
    image_name = os.environ.get("IMAGE_NAME", "supremeai-api:test")
    max_size_mb = int(os.environ.get("MAX_IMAGE_SIZE_MB", "500"))
    
    # ডকার ইমেজের টোটাল সাইজ বের করা
    size_cmd = f"docker image inspect {image_name} --format='{{{{.Size}}}}'"
    try:
        size_bytes = int(subprocess.check_output(size_cmd, shell=True).decode('utf-8').strip())
        size_mb = size_bytes / (1024 * 1024)
    except Exception as e:
        print(f"❌ Failed to get image size: {e}")
        sys.exit(1)

    print(f"📊 Current Image Size: {size_mb:.2f} MB")
    print(f"🎯 Target Max Size: {max_size_mb} MB")

    if size_mb <= max_size_mb:
        print("✅ Docker image size is strictly optimized. Proceeding...")
        sys.exit(0)

    print("🚨 BLOAT DETECTED! Image size exceeded limit. Initiating AI Autopsy...")
    
    # ডকারের কোন লেয়ারে কত এমবি ডেটা আছে তা বের করা
    history_cmd = f"docker history {image_name} --no-trunc --format '{{{{.Size}}}}\t{{{{.CreatedBy}}}}'"
    history_output = subprocess.check_output(history_cmd, shell=True).decode('utf-8')

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY missing. Failing build due to size bloat without AI analysis.")
        sys.exit(1)

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')

    prompt = f"""You are an elite DevSecOps AI. The CI/CD pipeline failed because the Docker image size ({size_mb:.2f} MB) exceeded the limit of {max_size_mb} MB.
    
    Analyze the following 'docker history' output. Identify EXACTLY which layers/commands are causing the bloat. 
    Provide a strict, bulleted action plan on how to fix it (e.g., adding specific files to .dockerignore, using multi-stage builds, or cleaning up apt caches).
    
    Docker History:
    {history_output}
    """

    response = model.generate_content(prompt)
    
    print("\n" + "="*50)
    print("🤖 SUPREMEAI DOCKER BLOAT ANALYSIS REPORT")
    print("="*50)
    print(response.text)
    print("="*50 + "\n")
    
    # গিটহাব অ্যাকশনস-এ রিপোর্ট দেখানোর জন্য
    with open("bloat_report.md", "w") as f:
        f.write(f"## 🚨 Docker Bloat Detected ({size_mb:.2f} MB)\n\n")
        f.write(response.text)

    # পাইপলাইন ফেইল (Fail) করানো
    print("💀 Failing the GitHub Action pipeline to prevent bloated deployment.")
    sys.exit(1)

if __name__ == "__main__":
    analyze_docker_bloat()
