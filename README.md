# Spatial Briefing

Daily architecture reading site built from ArchDaily, Dezeen, and Designboom.

## What it does

- fetches fresh articles from the three sources
- uses the OpenAI API to generate:
  - English learning text
  - Traditional Chinese translation
  - 5 architecture vocabulary items per article
  - simple everyday thinking prompts
  - English audio in multiple voices
- stores each day as a snapshot in `archive/YYYY-MM-DD.json`
- publishes the static site through GitHub Pages

## Local run

Set your environment variable first:

```bash
export OPENAI_API_KEY="your-key"
python3 generate_daily.py
```

This updates:

- `daily-content.js`
- `archive/index.json`
- `archive/YYYY-MM-DD.json`
- `audio/YYYY-MM-DD/*.mp3`

## GitHub setup

1. Create a new repository in the GitHub account you want to use.
2. Push this folder to the new repository.
3. In GitHub repo settings, add `OPENAI_API_KEY` under `Settings -> Secrets and variables -> Actions`.
4. In `Settings -> Pages`, set the source to `GitHub Actions`.
5. Run the `Daily Update` workflow once manually to verify the first generation.

The workflow then runs once a day at around `00:10` Taipei time.
