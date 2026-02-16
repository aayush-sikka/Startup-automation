import re

def find_emails(text: str):
    if not text:
        return []
    # Basic regex for email extraction
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    emails = re.findall(email_pattern, text)
    return list(set(emails))
