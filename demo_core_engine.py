"""
Integration demo showing the Search Engine and Ranker working together
This demonstrates the first two components of Phase 2: Core Engine
"""

import sys
import os
from pathlib import Path

# Add the parent directory to sys.path so we can import from core_engine
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

def demo_integration():
    """Demonstrate search engine and ranker working together"""
    print("=" * 70)
    print("SUPREMEAI CORE ENGINE INTEGRATION DEMO")
    print("Search Engine + Ranker = Intelligent Tool Discovery")
    print("=" * 70)
    
    # Import components
    from core_engine.multicatalog_search import MultiCatalogSearchEngine
    from core_engine.simple_ranker import SimpleToolRanker
    
    # Initialize the pipeline
    print("\n🔧 Initializing components...")
    search_engine = MultiCatalogSearchEngine()
    ranker = SimpleToolRanker()
    print("✅ Search Engine initialized")
    print("✅ Ranker initialized")
    
    # Example queries that would come from user requests
    test_queries = [
        "machine learning framework",
        "docker orchestration", 
        "web scraping library",
        "database migration tool",
        "API gateway"
    ]
    
    print(f"\n🔍 Processing {len(test_queries)} sample queries...")
    print("-" * 70)
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{i}. Query: '{query}'")
        print("   " + "─" * 50)
        
        # Step 1: Search across all catalogs
        search_results = search_engine.search(query, limit=8)
        print(f"   🔎 Found {len(search_results)} raw results from {len(search_engine.index)} sources")
        
        # Show top 3 raw results
        if search_results:
            print("   📋 Top 3 raw search results:")
            for j, result in enumerate(search_results[:3], 1):
                print(f"      {j}. [{result.source.value}] {result.name} "
                      f"(relevance: {result.relevance_score:.2f})")
        
        # Step 2: Rank the results using AI-powered scoring
        ranked_results = ranker.rank_results(search_results, query)
        print(f"   🏆 Ranked {len(ranked_results)} results")
        
        # Show top 3 ranked results
        if ranked_results:
            print("   🥇 Top 3 after AI ranking:")
            for j, ranked_result in enumerate(ranked_results[:3], 1):
                result = ranked_result.result
                improvement = ((ranked_result.total_score - result.relevance_score) / 
                              max(result.relevance_score, 0.1)) * 100
                print(f"      {j}. [{result.source.value}] {result.name}")
                print(f"         Score: {ranked_result.total_score:.3f} "
                      f"(+{improvement:.1f}% from base relevance)")
                if result.description:
                    desc = result.description[:60] + "..." if len(result.description) > 60 else result.description
                    print(f"         {desc}")
        
        print()
    
    print("=" * 70)
    print("✅ Core Engine Pipeline Complete!")
    print("   → Search Engine: Discovers candidates from multiple sources")
    print("   → Ranker: Applies AI scoring to surface the best options")
    print("   → Result: Intelligent tool discovery that goes beyond keyword matching")
    print("=" * 70)


if __name__ == "__main__":
    # Set up basic logging to keep output clean
    import logging
    logging.basicConfig(level=logging.WARNING)  # Reduce log noise
    demo_integration()