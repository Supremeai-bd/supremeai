#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================================
# file >> supreme-risk-scorer.py
# project >> SupremeAI 2.0
# purpose >> Core system functionality
# module >> scripts
# ============================================================================
import os
import json
import sys
import yaml
from pathlib import Path

class SupremeRiskScorer:
    def __init__(self):
        self.score = 0
        self.risk_factors = []
        
    def evaluate_config(self):
        audit_path = Path("audit_report.json")
        if audit_path.exists():
            with open(audit_path, "r") as f:
                report = json.load(f)
            for issue in report.get("issues", []):
                risk = issue.get("risk", "LOW")
                if risk == "CRITICAL":
                    self.score += 40
                    self.risk_factors.append(f"Critical Config Issue: {issue.get('message')}")
                elif risk == "HIGH":
                    self.score += 20
                    self.risk_factors.append(f"High Config Issue: {issue.get('message')}")
                elif risk == "MEDIUM":
                    self.score += 10
                    self.risk_factors.append(f"Medium Config Issue: {issue.get('message')}")

    def evaluate_docker(self):
        docker_path = Path("docker_analysis.json")
        if docker_path.exists():
            with open(docker_path, "r") as f:
                report = json.load(f)
            status = report.get("status")
            if status == "FAIL":
                self.score += 50
                self.risk_factors.append(f"Docker Size Exceeded Limit ({report.get('size_mb')}MB > {report.get('max_size_mb')}MB)")
            elif status == "WARN":
                self.score += 25
                self.risk_factors.append(f"Docker Size Warn Level Reached ({report.get('size_mb')}MB > {report.get('warn_size_mb')}MB)")

    def get_risk_rating(self):
        if self.score >= 70:
            return "CRITICAL"
        elif self.score >= 40:
            return "HIGH"
        elif self.score >= 15:
            return "MEDIUM"
        return "LOW"

    def run(self):
        self.evaluate_config()
        self.evaluate_docker()
        
        rating = self.get_risk_rating()
        
        result = {
            "score": min(self.score, 100),
            "rating": rating,
            "risk_factors": self.risk_factors,
            "status": "BLOCK" if rating == "CRITICAL" else "PASS"
        }
        
        print(json.dumps(result, indent=2))
        with open("risk_report.json", "w") as f:
            json.dump(result, f, indent=2)

if __name__ == '__main__':
    scorer = SupremeRiskScorer()
    scorer.run()
