🚀 Startup Agent Runtime (Groq-Powered)

A model-agnostic AI agent runtime built using Groq LLMs with structured tool-calling, strict execution boundaries, and schema validation.

This project demonstrates how to safely separate:

🧠 Planning (LLM reasoning)

🛠 Tool execution

✅ Structured output validation

🔒 Side-effect isolation

Designed for building safe, extensible AI agents.

✨ Features

Structured JSON tool-calling

Strict schema validation using Pydantic

Separation of planner and executor

Safe external tool boundaries

Modular tool architecture

Groq LLM integration

🏗 Architecture
User Input
    ↓
Planner (Groq LLM)
    ↓
Structured JSON Plan
    ↓
Schema Validation
    ↓
Tool Executor
    ↓
Final Response


The planner cannot execute tools directly.
All execution flows through a validated runtime layer.

📂 Project Structure
startup-agent/
│
├── main.py            # Entry point / API layer
├── planner.py         # LLM reasoning layer
├── executor.py        # Tool execution manager
├── schemas.py         # Structured output schemas
│
├── tools/
│   └── scraper.py     # Example external tool
│
├── requirements.txt
└── .env

⚙️ Installation
1️⃣ Clone the Repository
git clone https://github.com/aayush-sikka/startup-automation.git
cd startup-agent

2️⃣ Create Virtual Environment
python -m venv venv
venv\Scripts\activate    # Windows
source venv/bin/activate # Mac/Linux

3️⃣ Install Dependencies
pip install -r requirements.txt

🔑 Environment Variables

Create a .env file:

GROQ_API_KEY=your_groq_api_key_here

▶️ Running the App

If using FastAPI:

uvicorn main:app --reload


Open in browser:

http://127.0.0.1:8000/docs

🛠 Example Tool Call
Input
{
  "query": "Scrape https://example.com"
}

Planner Output
{
  "tool": "scrape_url",
  "arguments": {
    "url": "https://example.com"
  }
}

Final Response
{
  "result": "Extracted webpage content..."
}

🔒 Safety & Design Principles

JSON schema validation before execution

No direct tool execution from LLM

Strictly defined tool interfaces

Modular architecture for extensibility

Model-agnostic runtime design

📌 Use Cases

AI agent experimentation

Structured tool-calling systems

Research on safe LLM execution

Multi-model runtime experimentation

🚀 Future Improvements

Memory layer

Multi-step planning

Async tool execution

Logging & tracing

Multi-LLM provider support

🧑‍💻 Author

Built as an experimental structured AI agent runtime using Groq LLM APIs and safe execution principles.

If you'd like, I can now:

🔥 Make it more “startup founder” style

🎯 Make it more “resume/recruiter optimized”

📈 Add badges + professional polish

🧠 Convert it into a portfolio project page

Just tell me what vibe you want.
