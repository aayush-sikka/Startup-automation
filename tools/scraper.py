import requests
from bs4 import BeautifulSoup
import os

def scrape_website(url: str):
    user_agent = os.getenv("USER_AGENT", "Mozilla/5.0")
    try:
        headers = {'User-Agent': user_agent}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Get text content
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
            
        text = soup.get_text(separator=' ', strip=True)
        return text
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return ""
