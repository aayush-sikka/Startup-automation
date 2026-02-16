from langchain_groq import ChatGroq
from pydantic import BaseModel
from typing import List, Optional
import json


class Founder(BaseModel):
    name: str
    email: Optional[str] = None


class Startup(BaseModel):
    startup_name: str
    website: Optional[str] = None
    founded_year: Optional[str] = None
    founders: List[Founder]
    source_url: Optional[str] = None


llm = ChatGroq(
    model="llama3-8b-8192",
    temperature=0
)


def extract_startup_info(text: str):
    prompt = f"""
Extract startup details from the text below.

Return ONLY valid JSON in this format:

{{
  "startup_name": "",
  "website": "",
  "founded_year": "",
  "founders": [
    {{
      "name": "",
      "email": ""
    }}
  ],
  "source_url": ""
}}

Text:
{text[:10000]}
"""

    response = llm.invoke(prompt)
    content = response.content

    try:
        data = json.loads(content)
        return Startup(**data)
    except Exception:
        print("JSON parsing failed")
        print(content)
        return None
