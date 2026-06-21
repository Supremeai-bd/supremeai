import os
import xml.etree.ElementTree as ET
import re

def print_header(text):
    print(f"\n{'='*60}\n{text}\n{'='*60}")

def analyze_java_jacoco(report_path): # Changed to return gaps
    gaps = []
    if not os.path.exists(report_path):
        return gaps

    tree = ET.parse(report_path)
    root = tree.getroot()
    
    found_gaps = False
    for package in root.findall('package'):
        package_name = package.get('name')
        for sourcefile in package.findall('sourcefile'):
            file_name = sourcefile.get('name')
            # Look for line coverage
            line_counter = sourcefile.find("counter[@type='LINE']")
            if line_counter is not None:
                covered = int(line_counter.get('covered'))
                missed = int(line_counter.get('missed'))
                total = covered + missed
                percentage = (covered / total * 100) if total > 0 else 0
                
                if percentage < 50:  # Threshold for "Gap"
                    status = "EMPTY" if covered == 0 else "LOW"
                    gaps.append({
                        'file': f"{package_name.replace('.', '/')}/{file_name}",
                        'percentage': percentage,
                        'status': status,
                        'stack': 'Java'
                    })
    return gaps

def analyze_lcov(report_path, label): # Changed to return gaps
    gaps = []
    if not os.path.exists(report_path):
        return gaps

    with open(report_path, 'r') as f:
        content = f.read()

    sections = content.split('SF:')
    for section in sections[1:]:
        lines = section.split('\n')
        file_path = lines[0]
        
        # Match DA (Data) lines to find coverage
        da_lines = re.findall(r'DA:\d+,(\d+)', section)
        if da_lines:
            hits = sum(1 for h in da_lines if int(h) > 0)
            total = len(da_lines)
            percentage = (hits / total * 100) if total > 0 else 0
            
            if percentage < 50:
                status = "EMPTY" if hits == 0 else "LOW"
                gaps.append({
                    'file': file_path,
                    'percentage': percentage,
                    'status': status,
                    'stack': label.capitalize()
                })
    return gaps

def analyze_frontend_clover(report_path): # Changed to return gaps
    gaps = []
    if not os.path.exists(report_path):
        return gaps

    tree = ET.parse(report_path)
    root = tree.getroot()
    
    for project in root.findall('project'):
        for file in project.iter('file'):
            metrics = file.find('metrics')
            if metrics is not None:
                statements = int(metrics.get('statements', 0))
                covered = int(metrics.get('coveredstatements', 0))
                percentage = (covered / statements * 100) if statements > 0 else 0
                
                if percentage < 50:
                    status = "EMPTY" if covered == 0 else "LOW"
                    gaps.append({
                        'file': file.get('name'),
                        'percentage': percentage,
                        'status': status,
                        'stack': 'Frontend'
                    })
    return gaps

def get_coverage_gaps():
    """
    Aggregates coverage gaps from all configured report types.
    Returns a list of dictionaries, each representing a gap.
    """
    all_gaps = []
    
    # 1. Backend
    jacoco_xml = "build/reports/jacoco/test/jacocoTestReport.xml"
    all_gaps.extend(analyze_java_jacoco(jacoco_xml))
    
    # 2. Frontend
    frontend_clover = "dashboard/coverage/clover.xml"
    all_gaps.extend(analyze_frontend_clover(frontend_clover))
    
    # 3. Mobile
    mobile_lcov = "supremeai/coverage/lcov.info"
    all_gaps.extend(analyze_lcov(mobile_lcov, "MOBILE"))

    return all_gaps

def main():
    gaps = get_coverage_gaps()
    
    if not gaps:
        print("✅ No critical coverage gaps found across all projects.")
        return

    print_header("AGGREGATED COVERAGE GAPS (Threshold < 50%)")
    
    # Group and print for better readability
    for stack_type in ['Java', 'Frontend', 'Mobile']:
        stack_gaps = [g for g in gaps if g['stack'] == stack_type]
        if stack_gaps:
            print(f"\n--- {stack_type.upper()} ---")
            for gap in stack_gaps:
                print(f"[{gap['status']:5}] {gap['percentage']:5.1f}% | {gap['file']}")

    print(f"\nTotal critical gaps found: {len(gaps)}")

if __name__ == "__main__":
    main()