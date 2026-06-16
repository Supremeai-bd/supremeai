import os
import sys
import typer
from rich.console import Console
from rich.table import Table

# Add project root to sys path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brain.langgraph_agent import SupremeOrchestrator
from core.admin_god import AdminGodLayer
from core.universal_rules import UniversalRulesEngine

cli_app = typer.Typer(help="SupremeAI 2.0 Command Line Interface")
console = Console()

@cli_app.command()
def ask(
    task: str = typer.Option(..., "--task", "-t", help="Task prompt for the agent"),
    task_type: str = typer.Option("general", "--type", "-y", help="Task type (coding, image_generation, etc.)")
):
    """Asks SupremeAI 2.0 to solve a task."""
    console.print(f"[bold blue]Submitting task to SupremeAI Master Orchestrator:[/bold blue] {task}")
    
    rules = UniversalRulesEngine()
    admin = AdminGodLayer(rules)
    orchestrator = SupremeOrchestrator(admin)
    
    response = orchestrator.execute_task(task, task_type)
    
    if "Blocked" in response.get("result", ""):
        console.print(f"[bold red]EXECUTION BLOCKED:[/bold red] {response.get('result')}")
    else:
        console.print("[bold green]Response Result:[/bold green]")
        console.print(response.get("result", "No response output."))
        console.print(f"[yellow]Cost accumulated: ${response.get('cost', 0.0)}[/yellow]")

@cli_app.command()
def rules():
    """Lists all Constitutional Rules currently active."""
    rules_engine = UniversalRulesEngine()
    current_rules = rules_engine.rules
    
    table = Table(title="SupremeAI 2.0 Constitutional Rules")
    table.add_column("Rule Area", style="cyan")
    table.add_column("Configuration", style="magenta")
    
    for area, config in current_rules.items():
        table.add_row(area, str(config))
        
    console.print(table)

if __name__ == "__main__":
    cli_app()
