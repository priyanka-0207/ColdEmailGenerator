# 🚀 AI Cold Email Studio

An intelligent, context-aware automation platform for job-seekers. This tool uses **Retrieval-Augmented Generation (RAG)** to map your specific resume projects to job descriptions and schedules personalized outreach via secure **OAuth2/XOAuth2**.

-----

## ✨ Key Features

  * **Smart Context Retrieval (RAG):** Uses a vector database (**ChromaDB**) to inject only the most relevant parts of your resume into the LLM prompt.
  * **Secure Authentication:** Fully migrated from insecure SMTP passwords to **OAuth2 & XOAuth2** for Gmail and Outlook.
  * **LinkedIn Integration:** Connect your professional profile to pull live data for outreach personalization.
  * **Open Tracking:** Real-time dashboard to monitor when your emails are opened via a 1x1 tracking pixel.
  * **Scheduled Sending:** Queue your emails to be sent at optimal times using a robust SQLite-backed scheduler.

-----

## 🧠 The Tech Stack

| Component | Technology |
| :--- | :--- |
| **Backend** | Python / Flask |
| **AI/LLM** | Google Gemini / OpenAI GPT |
| **Vector DB** | ChromaDB |
| **Database** | SQLite / SQLAlchemy |
| **Auth** | OAuth2 / XOAuth2 (SASL) |
| **Frontend** | Jinja2 / Tailwind CSS |

-----

## 🛠️ Technical Deep Dive: Why RAG?

Most "AI generators" simply dump a full resume into a prompt, leading to "token bloat" and irrelevant content. This project solves that by:

1.  **Chunking:** Breaking your resume into semantic fragments.
2.  **Embedding:** Converting fragments into vectors using `sentence-transformers`.
3.  **Vector Search:** Querying **ChromaDB** to find the top 3 projects that match the *specific* Job Description provided.
4.  **Augmented Generation:** Passing only those 3 relevant projects to the LLM, ensuring a highly tailored and "human" tone.

-----

## 🚀 Getting Started

### 1\. Prerequisites

  * Python 3.10+
  * A Gmail or Outlook account (with OAuth Credentials)
  * An API Key (Gemini or OpenAI)

### 2\. Installation

```bash
# Clone the repository
git clone https://github.com/priyanka-0207/ColdEmailGenerator.git
cd ColdEmailGenerator

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # Or `.venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt
```

### 3\. Environment Setup

Create a `.env` file in the root directory:

```text
LINKEDIN_CLIENT_ID=your_id
LINKEDIN_CLIENT_SECRET=your_secret
LLM_API_KEY=your_key
SECRET_KEY=generate_a_random_string
```

### 4\. Run the App

```bash
python app.py
```

Visit `http://localhost:5000` to connect your accounts and start generating.

-----

## 🛡️ Security & Privacy

  * **No Stored Passwords:** We use OAuth2 tokens; your email password never touches our database.
  * **Local Processing:** Resume embeddings are stored locally in ChromaDB, not on a third-party cloud.

-----
