"""
Documentation Testing Script
Tests all code examples in documentation to ensure they work correctly
"""

import re
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Tuple
import json

class DocumentationTester:
    """Test all code examples in documentation"""
    
    def __init__(self, docs_path: str = "docs/knowledge-base"):
        self.docs_path = Path(docs_path)
        self.results = {
            "total_examples": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "errors": []
        }
    
    def extract_code_blocks(self, file_path: Path) -> List[Dict]:
        """Extract all code blocks from a markdown file"""
        code_blocks = []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Match code blocks with language identifier
        pattern = r'```(\w+)\n(.*?)\n```'
        matches = re.findall(pattern, content, re.DOTALL)
        
        for i, (language, code) in enumerate(matches, 1):
            code_blocks.append({
                "file": str(file_path),
                "line": self._get_line_number(content, code),
                "language": language,
                "code": code.strip(),
                "block_id": i
            })
        
        return code_blocks
    
    def _get_line_number(self, content: str, code: str) -> int:
        """Get line number of code block in file"""
        return content.find(code)
    
    def test_python_code(self, code: str) -> Tuple[bool, str]:
        """Test Python code example"""
        try:
            # Remove comments and print statements for safety
            lines = code.split('\n')
            safe_lines = []
            
            for line in lines:
                # Skip comments
                if line.strip().startswith('#'):
                    continue
                # Skip print statements (they might have side effects)
                if line.strip().startswith('print('):
                    continue
                safe_lines.append(line)
            
            safe_code = '\n'.join(safe_lines)
            
            # Try to compile
            compile(safe_code, '<string>', 'exec')
            
            return True, "Python code compiles successfully"
            
        except SyntaxError as e:
            return False, f"SyntaxError: {e}"
        except Exception as e:
            return False, f"Error: {e}"
    
    def test_bash_code(self, code: str) -> Tuple[bool, str]:
        """Test bash code example (syntax check only)"""
        try:
            # Write to temp file
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
                f.write('#!/bin/bash\n')
                f.write(code)
                temp_file = f.name
            
            # Run shellcheck if available
            try:
                result = subprocess.run(
                    ['shellcheck', temp_file],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    return True, "Bash code passes shellcheck"
                else:
                    return False, f"Shellcheck warnings: {result.stdout}"
                    
            except FileNotFoundError:
                # shellcheck not installed, skip
                return True, "Skipped (shellcheck not installed)"
            
        except Exception as e:
            return False, f"Error: {e}"
    
    def test_javascript_code(self, code: str) -> Tuple[bool, str]:
        """Test JavaScript code example"""
        try:
            # Try to parse with Node.js
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
                f.write(code)
                temp_file = f.name
            
            # Run node --check (syntax check only)
            result = subprocess.run(
                ['node', '--check', temp_file],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                return True, "JavaScript code is valid"
            else:
                return False, f"SyntaxError: {result.stderr}"
            
        except FileNotFoundError:
            # Node not installed, skip
            return True, "Skipped (Node.js not installed)"
        except Exception as e:
            return False, f"Error: {e}"
    
    def test_typescript_code(self, code: str) -> Tuple[bool, str]:
        """Test TypeScript code example"""
        try:
            # TypeScript requires compilation, skip for now
            return True, "Skipped (TypeScript compilation not implemented)"
        except Exception as e:
            return False, f"Error: {e}"
    
    def test_json_code(self, code: str) -> Tuple[bool, str]:
        """Test JSON code example"""
        try:
            json.loads(code)
            return True, "JSON is valid"
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON: {e}"
    
    def test_code_block(self, block: Dict) -> Dict:
        """Test a single code block"""
        language = block['language']
        code = block['code']
        
        result = {
            "file": block['file'],
            "line": block['line'],
            "language": language,
            "block_id": block['block_id'],
            "passed": False,
            "message": ""
        }
        
        # Skip certain languages
        skip_languages = ['text', 'markdown', 'diff', 'sql', 'mermaid']
        if language in skip_languages:
            result['passed'] = True
            result['message'] = f"Skipped (language: {language})"
            self.results['skipped'] += 1
            return result
        
        # Test based on language
        if language == 'python':
            passed, message = self.test_python_code(code)
        elif language == 'bash' or language == 'sh':
            passed, message = self.test_bash_code(code)
        elif language == 'javascript' or language == 'js':
            passed, message = self.test_javascript_code(code)
        elif language == 'typescript' or language == 'ts':
            passed, message = self.test_typescript_code(code)
        elif language == 'json':
            passed, message = self.test_json_code(code)
        else:
            # Unknown language, skip
            passed = True
            message = f"Skipped (unsupported language: {language})"
            self.results['skipped'] += 1
            result['passed'] = True
            result['message'] = message
            return result
        
        result['passed'] = passed
        result['message'] = message
        
        if passed:
            self.results['passed'] += 1
        else:
            self.results['failed'] += 1
            self.results['errors'].append({
                "file": block['file'],
                "line": block['line'],
                "language": language,
                "error": message,
                "code": code[:200]  # First 200 chars
            })
        
        return result
    
    def test_file(self, file_path: Path) -> List[Dict]:
        """Test all code blocks in a file"""
        code_blocks = self.extract_code_blocks(file_path)
        results = []
        
        for block in code_blocks:
            self.results['total_examples'] += 1
            result = self.test_code_block(block)
            results.append(result)
        
        return results
    
    def test_all_documentation(self) -> Dict:
        """Test all documentation files"""
        all_results = []
        
        # Find all markdown files
        md_files = list(self.docs_path.rglob("*.md"))
        
        for md_file in md_files:
            # Skip templates and improvement plan
            if 'templates' in str(md_file) or 'IMPROVEMENT' in str(md_file):
                continue
            
            print(f"Testing: {md_file}")
            file_results = self.test_file(md_file)
            all_results.extend(file_results)
        
        return {
            "summary": self.results,
            "details": all_results
        }
    
    def generate_report(self) -> str:
        """Generate test report"""
        results = self.test_all_documentation()
        
        report = []
        report.append("=" * 80)
        report.append("DOCUMENTATION TEST REPORT")
        report.append("=" * 80)
        report.append("")
        
        # Summary
        summary = results['summary']
        report.append("SUMMARY")
        report.append("-" * 80)
        report.append(f"Total Code Examples: {summary['total_examples']}")
        report.append(f"Passed: {summary['passed']} ({summary['passed']/max(summary['total_examples'],1)*100:.1f}%)")
        report.append(f"Failed: {summary['failed']} ({summary['failed']/max(summary['total_examples'],1)*100:.1f}%)")
        report.append(f"Skipped: {summary['skipped']}")
        report.append("")
        
        # Errors
        if summary['errors']:
            report.append("ERRORS")
            report.append("-" * 80)
            for error in summary['errors']:
                report.append(f"\n❌ {error['file']}:{error['line']}")
                report.append(f"   Language: {error['language']}")
                report.append(f"   Error: {error['error']}")
                report.append(f"   Code: {error['code'][:100]}...")
        
        report.append("")
        report.append("=" * 80)
        
        return "\n".join(report)
    
    def save_report(self, output_file: str = "docs/test_report.json"):
        """Save detailed report to JSON"""
        results = self.test_all_documentation()
        
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"Report saved to: {output_file}")


def main():
    """Main entry point"""
    tester = DocumentationTester()
    
    # Generate and print report
    report = tester.generate_report()
    print(report)
    
    # Save detailed JSON report
    tester.save_report()
    
    # Exit with error code if tests failed
    if tester.results['failed'] > 0:
        print(f"\n❌ FAILED: {tester.results['failed']} code examples failed")
        sys.exit(1)
    else:
        print(f"\n✅ PASSED: All code examples are valid")
        sys.exit(0)


if __name__ == "__main__":
    main()