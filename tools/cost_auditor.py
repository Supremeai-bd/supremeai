import os
from typing import Dict
import matplotlib.pyplot as plt
from loguru import logger
from memory.sqlite_store import SQLiteMemoryStore

class CostAuditor:
    def __init__(self, db_path: str = None):
        self.store = SQLiteMemoryStore(db_path)
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.report_dir = os.path.join(base_dir, "data")
        os.makedirs(self.report_dir, exist_ok=True)

    def generate_report(self) -> Dict[str, str]:
        tasks = self.store.get_task_history()
        
        # If no task data exists, populate with mock data for demonstration
        if not tasks:
            logger.info("No task history found. Populating mock data for cost auditing report.")
            mock_data = [
                ("Code validation", "coding", 0.05),
                ("Factual check", "general", 0.02),
                ("Translation task", "translation", 0.01),
                ("Math solving", "reasoning", 0.15),
                ("Search RAG", "general", 0.04),
            ]
            for desc, t_type, cost in mock_data:
                self.store.log_task(desc, t_type, True, cost, "Completed")
            tasks = self.store.get_task_history()

        total_cost = sum(t["cost"] for t in tasks)
        by_type: Dict[str, float] = {}
        for t in tasks:
            t_type = t["task_type"]
            by_type[t_type] = by_type.get(t_type, 0.0) + t["cost"]

        # 1. Generate text report (markdown)
        text_report_path = os.path.join(self.report_dir, "cost_report.md")
        with open(text_report_path, "w", encoding="utf-8") as f:
            f.write("# 📊 Monthly Cost Audit Report\n\n")
            f.write(f"- **Total API Cost:** ${total_cost:.4f}\n")
            f.write(f"- **Total Tasks Processed:** {len(tasks)}\n\n")
            f.write("## Cost Breakdown by Task Type\n\n")
            f.write("| Task Type | Cost ($) | Percentage |\n")
            f.write("| --- | --- | --- |\n")
            for t_type, cost in by_type.items():
                pct = (cost / total_cost * 100) if total_cost > 0 else 0
                f.write(f"| {t_type} | ${cost:.4f} | {pct:.1f}% |\n")

        # 2. Generate graphical image report using matplotlib
        image_report_path = os.path.join(self.report_dir, "cost_report.png")
        try:
            fig, ax = plt.subplots(figsize=(6, 4))
            types = list(by_type.keys())
            costs = list(by_type.values())
            
            ax.bar(types, costs, color="skyblue")
            ax.set_title("API Costs by Task Type")
            ax.set_xlabel("Task Type")
            ax.set_ylabel("Cost ($)")
            
            plt.tight_layout()
            plt.savefig(image_report_path, dpi=150)
            plt.close()
            logger.info(f"Cost reports generated successfully. Image: {image_report_path}, Text: {text_report_path}")
        except Exception as e:
            logger.error(f"Failed to generate cost report image: {e}")

        return {
            "text_report": text_report_path,
            "image_report": image_report_path
        }
