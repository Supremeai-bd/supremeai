"""
Base scraper class for SupremeAI resource collection
Provides common functionality for scraping various awesome lists and resource sites
"""

import abc
import json
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import urllib.request
import urllib.error


class BaseResourceScraper(ABC):
    """Base class for all resource scrapers"""
    
    def __init__(self, name: str, data_dir: Path):
        self.name = name
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.logger = self._setup_logger()
        
    def _setup_logger(self) -> logging.Logger:
        """Set up logging for the scraper"""
        logger = logging.getLogger(f"scraper.{self.name}")
        logger.setLevel(logging.INFO)
        
        # Create file handler
        log_file = self.data_dir / f"{self.name}.log"
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.INFO)
        
        # Create console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        
        # Add handlers if not already added
        if not logger.handlers:
            logger.addHandler(fh)
            logger.addHandler(ch)
            
        return logger
    
    @abstractmethod
    def fetch_data(self) -> Any:
        """Fetch raw data from the source"""
        pass
    
    @abstractmethod
    def parse_data(self, raw_data: Any) -> List[Dict[str, Any]]:
        """Parse raw data into standardized format"""
        pass
    
    def save_data(self, data: List[Dict[str, Any]], filename: str = None) -> Path:
        """Save parsed data to JSON file"""
        if filename is None:
            filename = f"{self.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        filepath = self.data_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Saved {len(data)} items to {filepath}")
        return filepath
    
    def load_latest_data(self) -> Optional[List[Dict[str, Any]]]:
        """Load the most recently saved data file"""
        json_files = list(self.data_dir.glob(f"{self.name}_*.json"))
        if not json_files:
            return None
        
        # Sort by modification time, get latest
        latest_file = max(json_files, key=lambda f: f.stat().st_mtime)
        
        try:
            with open(latest_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.logger.info(f"Loaded {len(data)} items from {latest_file}")
            return data
        except Exception as e:
            self.logger.error(f"Failed to load data from {latest_file}: {e}")
            return None
    
    def run(self) -> Optional[Path]:
        """Execute the full scraping process"""
        try:
            self.logger.info(f"Starting scrape for {self.name}")
            start_time = time.time()
            
            # Fetch raw data
            raw_data = self.fetch_data()
            if raw_data is None:
                self.logger.error("Failed to fetch data")
                return None
            
            # Parse data
            parsed_data = self.parse_data(raw_data)
            if not parsed_data:
                self.logger.warning("No data parsed from source")
                return None
            
            # Save data
            filepath = self.save_data(parsed_data)
            
            elapsed_time = time.time() - start_time
            self.logger.info(f"Scrape completed in {elapsed_time:.2f} seconds")
            
            return filepath
            
        except Exception as e:
            self.logger.error(f"Error during scrape: {e}", exc_info=True)
            return None


class AwesomeListScraper(BaseResourceScraper):
    """Scraper for awesome-* lists on GitHub"""
    
    def __init__(self, name: str, repo_url: str, data_dir: Path):
        super().__init__(name, data_dir)
        self.repo_url = repo_url
        self.readme_url = f"{repo_url.replace('github.com', 'raw.githubusercontent.com')}/master/README.md"
    
    def fetch_data(self) -> Optional[str]:
        """Fetch README.md from GitHub"""
        try:
            self.logger.info(f"Fetching README from {self.readme_url}")
            with urllib.request.urlopen(self.readme_url) as response:
                return response.read().decode('utf-8')
        except urllib.error.URLError as e:
            self.logger.error(f"Failed to fetch README: {e}")
            return None
    
    def parse_data(self, content: str) -> List[Dict[str, Any]]:
        """Parse awesome list README into structured data"""
        lines = content.split('\n')
        categories = {}
        current_category = None
        
        for line in lines:
            # Check for category heading (## Category Name)
            if line.startswith('## '):
                current_category = line[3:].strip()
                categories[current_category] = []
            # Check for list item that looks like: - [name](url) - description
            elif current_category and line.strip().startswith('- ['):
                # Extract the part between - [ and ]
                import re
                match = re.match(r'\s*-\s*\[([^\]]+)\]\(([^)]+)\)\s*-\s*(.+)', line.strip())
                if match:
                    name, url, description = match.groups()
                    categories[current_category].append({
                        "name": name.strip(),
                        "url": url.strip(),
                        "description": description.strip(),
                        "category": current_category
                    })
                else:
                    # Try without description
                    match = re.match(r'\s*-\s*\[([^\]]+)\]\(([^)]+)\)', line.strip())
                    if match:
                        name, url = match.groups()
                        categories[current_category].append({
                            "name": name.strip(),
                            "url": url.strip(),
                            "description": "",
                            "category": current_category
                        })
        
        # Flatten the structure
        all_items = []
        for category_items in categories.values():
            all_items.extend(category_items)
        
        return all_items