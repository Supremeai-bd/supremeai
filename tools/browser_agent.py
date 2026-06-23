#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================================
# file >> browser_agent.py
# project >> SupremeAI 2.0
# purpose >> AI agent management
# module >> tools
# ============================================================================
import httpx
from bs4 import BeautifulSoup
from loguru import logger
from typing import Dict, Any

class BrowserAgent:
    """Controls browser actions and scrapes website data."""
    def __init__(self):
        pass
        
    def fetch_page(self, url: str) -> Dict[str, Any]:
        logger.info(f"Scraping web page: {url}")
        try:
            # Add simple user agent header to prevent blocking
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            response = httpx.get(url, headers=headers, timeout=10.0, follow_redirects=True)
            response.raise_for_status()
            
            # Simple title and content parser
            soup = BeautifulSoup(response.text, "html.parser")
            title = soup.title.string if soup.title else "No Title"
            
            # Extract main text
            for script in soup(["script", "style"]):
                script.extract()
            text = soup.get_text(separator=" ")
            clean_text = " ".join(text.split())[:2000] # Cap text length
            
            return {
                "success": True,
                "url": url,
                "title": title,
                "content": clean_text
            }
        except Exception as e:
            logger.error(f"Failed to scrape {url}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
