"""
AI-Powered Tool Ranker for SupremeAI Core Engine
Simplified demonstration version
"""

import logging
from typing import List, Dict, Any
from dataclasses import dataclass
import sys
import os

# Add the current directory to the path so we can import multicatalog_search
sys.path.insert(0, os.path.dirname(__file__))

from multicatalog_search import SearchResult, CatalogSource


@dataclass
class RankedResult:
    """A search result with ranking scores"""
    result: SearchResult
    total_score: float
    rank: int


class SimpleToolRanker:
    """
    Simple tool ranker that demonstrates the concept
    """
    
    def __init__(self):
        self.logger = self._setup_logger()
    
    def _setup_logger(self) -> logging.Logger:
        """Set up logging for the ranker"""
        logger = logging.getLogger("simple_ranker")
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger
    
    def rank_results(
        self, 
        results: List[SearchResult], 
        query: str = ""
    ) -> List[RankedResult]:
        """
        Rank a list of search results (simplified version)
        
        Args:
            results: List of search results to rank
            query: Original search query
            
        Returns:
            List of RankedResult objects sorted by score (descending)
        """
        if not results:
            return []
            
        self.logger.info(f"Ranking {len(results)} results for query: '{query}'")
        
        # Simple ranking: combine search relevance with some basic factors
        ranked_results = []
        
        for result in results:
            # Start with the search relevance score
            base_score = result.relevance_score
            
            # Add some simple boosting factors based on source
            source_bonus = {
                'awesome-selfhosted': 0.1,
                'awesome-go': 0.05,
                'awesome-python': 0.05,
                'ossinsight': 0.15  # OSS Insight gets a boost for curated data
            }.get(result.source.value, 0.0)
            
            # Calculate total score
            total_score = min(1.0, base_score + source_bonus)
            
            ranked_result = RankedResult(
                result=result,
                total_score=total_score,
                rank=0  # Will be set after sorting
            )
            
            ranked_results.append(ranked_result)
        
        # Sort by total score (descending)
        ranked_results.sort(key=lambda x: x.total_score, reverse=True)
        
        # Assign ranks
        for i, ranked_result in enumerate(ranked_results):
            ranked_result.rank = i + 1
            
        self.logger.info(f"Ranking complete. Top score: {ranked_results[0].total_score:.3f}" if ranked_results else "No results to rank")
        
        return ranked_results


def demo_ranker():
    """Demonstration of the ranker functionality"""
    print("=" * 60)
    print("SUPREMEAI SIMPLE TOOL RANKER DEMO")
    print("=" * 60)
    
    # Import the search engine to get some results to rank
    from multicatalog_search import MultiCatalogSearchEngine
    
    # Initialize components
    search_engine = MultiCatalogSearchEngine()
    ranker = SimpleToolRanker()
    
    # Get some search results
    query = "docker"
    search_results = search_engine.search(query, limit=10)
    
    print(f"\nOriginal search results for '{query}' ({len(search_results)} found):")
    for i, result in enumerate(search_results[:5], 1):
        print(f"  {i}. [{result.source.value}] {result.name} (score: {result.relevance_score:.2f})")
    
    # Rank the results
    ranked_results = ranker.rank_results(search_results, query)
    
    print(f"\nRanked results for '{query}':")
    for i, ranked_result in enumerate(ranked_results[:5], 1):
        result = ranked_result.result
        print(f"  {i}. [{result.source.value}] {result.name}")
        print(f"     Rank Score: {ranked_result.total_score:.3f}")
        print(f"     Original Relevance: {result.relevance_score:.2f}")
        if result.description:
            desc = result.description[:80] + "..." if len(result.description) > 80 else result.description
            print(f"     Description: {desc}")
        print()
    
    print("=" * 60)
    print("Ranker demo complete")


if __name__ == "__main__":
    # Configure logging for demo
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    demo_ranker()