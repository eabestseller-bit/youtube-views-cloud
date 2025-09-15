# YouTubeViews_Cloud (deploy-ready)

Deploy options (choose one):

## A) Render (recommended, easy UI)
1. Push these files to a new GitHub repo.
2. On Render.com → New + → Web Service → Connect your repo.
3. Select:
   - Runtime: Python
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app`
4. Set the environment variable:
   - `YOUTUBE_API_KEY=YOUR_KEY`
5. Deploy. After "Live", open the public URL and use the form.

## B) Railway / Fly.io / Heroku
- Use the same `requirements.txt` and `Procfile`.
- Set `YOUTUBE_API_KEY` env variable in project settings.
- Start command: `gunicorn app:app`

## Security
- Never commit your real API key to the repo.
- Keep `YOUTUBE_API_KEY` in the provider's env vars.
