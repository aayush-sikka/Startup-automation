import requests
import json
import os

def search_startups(query: str, n_results: int = 5):
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        print("Warning: SERPER_API_KEY not found in environment variables.")
        return {}
        
    url = "https://google.serper.dev/search"
    payload = json.dumps({"q": query, "num": n_results})
    headers = {
        'X-API-KEY': api_key,
        'Content-Type': 'application/json'
    }
    try:
        response = requests.request("POST", url, headers=headers, data=payload)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error searching for startups: {e}")
        return {}
