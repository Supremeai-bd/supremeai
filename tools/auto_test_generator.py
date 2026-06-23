#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================================
# file >> auto_test_generator.py
# project >> SupremeAI 2.0
# purpose >> Unit testing and QC
# module >> tools
# ============================================================================
import os
import sys
import subprocess
from typing import Dict, Any

# Ensure UTF-8 console output on Windows
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Add project root to PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# Assuming coverage_auditor.py and bangla_ai_connector.py are in the same directory or accessible via sys.path
try:
    from scripts.tools.coverage_auditor import get_coverage_gaps
    from scripts.tools.bangla_ai_connector import BanglaAiConnector
except ImportError:
    print("Error: Could not import coverage_auditor or bangla_ai_connector. Please check paths.")
    # Fallback for local testing if imports fail
    def get_coverage_gaps():
        return [
            {"file": "src/main/java/com/supremeai/service/UserService.java", "percentage": 0.0, "status": "EMPTY", "stack": "Java"},
            {"file": "dashboard/src/components/UserCard.tsx", "percentage": 10.0, "status": "LOW", "stack": "Frontend"},
            {"file": "supremeai/lib/screens/login_screen.dart", "percentage": 0.0, "status": "EMPTY", "stack": "Mobile"}
        ]
    class BanglaAiConnector:
        def __init__(self, credentials=None):
            print("Using dummy BanglaAiConnector")
        def authenticate(self):
            print("Dummy AI authentication successful.")
            return True
        def call_api(self, prompt: str) -> Dict[str, Any]:
            print(f"Dummy AI call with prompt: {prompt[:100]}...")
            # Simulate AI response for test code
            if "Java" in prompt:
                return {"success": True, "data": {"generated_text": "// Java Test Code for " + prompt.split("SOURCE CODE:")[0].split("for ")[1].strip().split("\n")[0] + "\npublic class GeneratedTest { /* ... */ }"}}
            elif "Frontend" in prompt:
                return {"success": True, "data": {"generated_text": "// Frontend Test Code for " + prompt.split("SOURCE CODE:")[0].split("for ")[1].strip().split("\n")[0] + "\ndescribe('Generated Component', () => { /* ... */ });"}}
            elif "Mobile" in prompt:
                return {"success": True, "data": {"generated_text": "// Mobile Test Code for " + prompt.split("SOURCE CODE:")[0].split("for ")[1].strip().split("\n")[0] + "\nvoid main() { /* ... */ }"}}
            return {"success": False, "error": "AI generation failed"}


def print_header(text):
    print(f"\n{'='*60}\n{text}\n{'='*60}")

def call_ai_to_generate_test(file_path: str, code_content: str, stack_type: str) -> str:
    """
    Calls the AI model to generate test code for the given source file.
    """
    ai_connector = BanglaAiConnector() # Assuming credentials are handled internally or via env vars
    if not ai_connector.authenticate():
        print("[ERROR] AI authentication failed. Cannot generate tests.")
        return ""

    prompt = f"""
    Generate a comprehensive unit test for the following {stack_type} code.
    Follow the project's testing patterns (JUnit 5 for Java, Vitest/Jest for Frontend, Flutter test for Mobile).
    Ensure 80%+ coverage. Focus on critical paths, edge cases, and error handling.

    SOURCE FILE: {file_path}
    STACK TYPE: {stack_type}
    SOURCE CODE:
    ```
    {code_content}
    ```
    """
    print(f"[AI] Requesting test generation for {file_path} ({stack_type})...")
    
    try:
        response = ai_connector.call_api(prompt)
        if response.get("success") and response.get("data", {}).get("generated_text"):
            print(f"[AI] Successfully received test code for {file_path}.")
            return response["data"]["generated_text"]
        else:
            print(f"[ERROR] AI generation failed for {file_path}: {response.get('error', 'Unknown error')}")
            return ""
    except Exception as e:
        print(f"[ERROR] Exception during AI call for {file_path}: {e}")
        return ""

def get_test_file_path(original_file_path: str, stack_type: str) -> str:
    """
    Determines the appropriate test file path based on the original file and stack type.
    """
    if stack_type == "Java":
        # Example: src/main/java/com/supremeai/service/UserService.java
        # Becomes: src/test/java/com/supremeai/service/UserServiceTest.java
        return original_file_path.replace("src/main/java", "src/test/java").replace(".java", "Test.java")
    elif stack_type == "Frontend":
        # Example: dashboard/src/components/UserCard.tsx
        # Becomes: dashboard/src/components/UserCard.test.tsx (or .spec.tsx)
        base_name, ext = os.path.splitext(original_file_path)
        return f"{base_name}.test{ext}"
    elif stack_type == "Mobile":
        # Example: supremeai/lib/screens/login_screen.dart
        # Becomes: supremeai/test/screens/login_screen_test.dart
        return original_file_path.replace("lib/", "test/").replace(".dart", "_test.dart")
    return ""

def main():
    """
    Main function to orchestrate autonomous test generation.
    """
    print_header("🚀 Starting Autonomous Test Generation...")
    
    # 1. Get coverage gaps from the auditor
    gaps = get_coverage_gaps()
    
    if not gaps:
        print("✅ No critical coverage gaps found. No tests to generate.")
        return

    print(f"Found {len(gaps)} files with critical coverage gaps (below 50%).")
    
    generated_count = 0
    passed_count = 0
    for gap in gaps:
        file_path = gap["file"]
        stack = gap["stack"]
        
        # Adjust file_path for Java if it's in package format
        if stack == 'Java' and not file_path.startswith("src/main/java"):
             file_path = f"src/main/java/{file_path}" # Prepend base path if missing

        if not os.path.exists(file_path):
            print(f"[WARNING] Source file not found, skipping: {file_path}")
            continue
            
        # 2. Read source code
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"[ERROR] Could not read source file {file_path}: {e}")
            continue
            
        # 3. AI generates test code
        test_code = call_ai_to_generate_test(file_path, content, stack)
        
        if test_code:
            # 4. Save test file
            test_file_path = get_test_file_path(file_path, stack)
            if test_file_path:
                try:
                    os.makedirs(os.path.dirname(test_file_path), exist_ok=True)
                    with open(test_file_path, 'w', encoding='utf-8') as f:
                        f.write(test_code)
                    print(f"📝 Created test file: {test_file_path}")
                    generated_count += 1
                    
                    # 5. Run the newly generated test
                    print(f"🧪 Running newly generated test: {test_file_path}")
                    test_command = []
                    if stack == "Java":
                        # Convert file path to fully qualified class name
                        # e.g., src/test/java/com/supremeai/service/UserServiceTest.java -> com.supremeai.service.UserServiceTest
                        fqcn = test_file_path.replace("src/test/java/", "").replace(".java", "").replace("/", ".")
                        test_command = ["./gradlew", "test", "--tests", fqcn]
                    elif stack == "Frontend":
                        # Path relative to dashboard directory
                        relative_path = os.path.relpath(test_file_path, "dashboard")
                        test_command = ["npm", "test", "-w", "dashboard", "--", relative_path]
                    elif stack == "Mobile":
                        # Path relative to supremeai directory
                        relative_path = os.path.relpath(test_file_path, "supremeai")
                        test_command = ["flutter", "test", relative_path]
                    
                    if test_command:
                        try:
                            # Use shell=True for Windows batch commands like gradlew, npm
                            # capture_output=True to suppress direct output unless needed for debugging
                            result = subprocess.run(test_command, check=False, shell=True, capture_output=True, text=True)
                            if result.returncode == 0:
                                print(f"✅ Test passed for {test_file_path}")
                                passed_count += 1
                            else:
                                print(f"❌ Test FAILED for {test_file_path}")
                                print("--- Test Output ---")
                                print(result.stdout)
                                print(result.stderr)
                                print("-------------------")
                        except FileNotFoundError:
                            print(f"[ERROR] Test runner not found for {stack}. Command: {' '.join(test_command)}")
                        except Exception as e:
                            print(f"[ERROR] Failed to run test for {test_file_path}: {e}")
                    else:
                        print(f"[WARNING] No test command defined for stack: {stack}")
                except Exception as e:
                    print(f"[ERROR] Could not write test file {test_file_path}: {e}")
            else:
                print(f"[ERROR] Could not determine test file path for {file_path} (stack: {stack})")
        else:
            print(f"[WARNING] No test code generated for {file_path}.")
    
    print_header(f"Autonomous Test Generation Completed. Generated {generated_count} new test files, {passed_count} passed.")

if __name__ == "__main__":
    main()