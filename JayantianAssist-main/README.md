# JayantianAssist: Kristu Jayanti University chatbot

Sign up, log in and chat. Answers come from content of https://kristujayanti.edu.in/.

## Run
```
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000. Set `SECRET_KEY` in the environment for anything beyond local testing.

## Files
- `app.py` Flask app: `/signup`, `/login`, `/forgot-password`, `/chat`, `/api/chat`, `/logout`
- `chatbot.py` NLP engine (tokenise, stem, synonyms, BM25 ranking). Test in terminal: `python chatbot.py`
- `data/knowledge_base.json` website content in chunks (edit/add entries to teach the bot)
- `scrape_site.py` optional crawler to refresh data from the live site
- `templates/`, `static/` pages and styling

## Email rule
Sign-up accepts only `name@kristujayanti.com` (checked in the browser and again on the server in `app.py`, `EMAIL_RE`).

## Optional: Claude-written answers
`pip install anthropic` and set `ANTHROPIC_API_KEY`. The bot then writes a natural answer using only the retrieved passages. Without it, the passages are shown directly.

## Known limits
- Emails are not verified by a link or OTP, so anyone can type any `@kristujayanti.com` address. Add email verification before a public launch.
- Some details (MCA/MBA fees, hostel fees, Wi-Fi) were not on the website pages that were read, so the bot refers to the helpdesk.
