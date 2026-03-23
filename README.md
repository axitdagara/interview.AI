# AI-Based Interview Simulator with Intelligent Feedback

A complete final-year project built with Flask, SQLite, and NLP scoring.

## Features

- User authentication (register, login, logout)
- Interview categories: HR, Technical, Aptitude, Behavioral
- Live AI question generation from Interview Setup (Groq API)
- Timer-based interview simulation
- AI evaluation using TF-IDF + cosine similarity
- Smart feedback with missing keywords
- Voice input for answers (browser speech-to-text)
- Performance dashboard with charts
- Resume analyzer (PDF upload, AI role-fit scoring and improvement tips)
- Session history and CSV report export

## Tech Stack

- Python
- Flask
- Flask-Login
- Flask-SQLAlchemy
- Scikit-learn
- PyPDF2
- HTML, CSS, Bootstrap, Chart.js
- SQLite

## Project Structure

```
run.py
requirements.txt
interview_simulator/
  __init__.py
  config.py
  extensions.py
  models.py
  seed.py
  routes/
    __init__.py
    main.py
    auth.py
    interview.py
    dashboard.py
    resume.py
  services/
    evaluator.py
    resume_parser.py
  templates/
    base.html
    index.html
    register.html
    login.html
    interview_setup.html
    interview_question.html
    interview_result.html
    dashboard.html
    history.html
    resume_analyzer.html
  static/
    css/style.css
    js/main.js
```

## Setup Instructions

1. Create a virtual environment and activate it.

   Windows PowerShell:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. Install dependencies.

   ```powershell
   pip install -r requirements.txt
   ```

3. Run the app.

   ```powershell
   python run.py
   ```

4. Open in browser.

   ```
   http://127.0.0.1:5000
   ```

## Real AI Question Generation (Groq)

Use **Interview Setup** and select **Question Source = AI Live (Grok)** to generate fresh MCQ questions for each round.

Set environment variables before running:

```powershell
$env:AI_PROVIDER_DEFAULT="groq"
$env:GROQ_API_KEY="your_groq_api_key"
$env:GROQ_MODEL="llama-3.3-70b-versatile"
$env:GROQ_API_BASE_URL="https://api.groq.com/openai/v1"
```

Notes:

- The app is configured for Groq by default.
- Legacy `GROK_*` variables are still accepted for backward compatibility.
- Newly generated categories are saved directly in the same question bank.

## Viva Notes

- NLP uses TF-IDF vectorization and cosine similarity to compute answer relevance score.
- Score is mapped to qualitative feedback bands.
- Missing important keywords are shown for improvement.
- Dashboard includes weak category and trend analytics for measurable progress.

## Future Enhancements

- LLM-based semantic scoring
- Video interview and emotion analysis
- Multi-language support
- Adaptive follow-up questions
