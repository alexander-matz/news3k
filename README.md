# news3k

News3k is a minimal news aggregator based on the python library `newspaper3k`.
It shows an overview of the articles of all configured news sources with their
title, a summary, and a link to its full text.

The software is split into two parts, connected via an sqlite database:

1. The commandline backend manages news sources and scrapes theses sources for
   articles.
   It does not run automatically but is either manually invoked by the user or
   set up for repeated execution via cron or similar.
2. The web frontend provides a compact view of the scraped news articles and is
   implemented as a flask web server.

# Usage

Before starting you need to ensure you have `python` installed (the software is
tested with versions 3.6 and 3.7) and have the following python libraries:

- `newspaper3k`, news scraping library
- `iso8601`, time parsing library required when using `python` <3.6
- `click`, modular cli required by the backend
- `flask`, web framework required by the web frontend

If all dependencies are met, configure some news sources, scrape articles and
start the webserver:

```bash
$ ./news3k.py add-source 'https://<your news source>.com' news
total: 190, new: 10, blocked: 180 failed: 0

$ ./news3k.py add-source 'https://<your other news source>.com' news
total: 1870, new: 10, blocked: 1860 failed: 0

$ ./news3k.py fetch-articles
collecting: https://<your news source>.com
total: 193, new: 3, failed: 0
collecting: https://<your other news source>.com
total: 189, new: 9, failed: 0

$ FLASK_APP=news3k-web.py flask run
 * Serving Flask app "news3k-web.py"
 * Environment: production
   WARNING: Do not use the development server in a production environment.
   Use a production WSGI server instead.
 * Debug mode: off
 * Running on http://127.0.0.1:5000/ (Press CTRL+C to quit)
```

Execute `$ ./news3k.py` without a command to see the command list.

Use your platforms mechanism to periodically scrape articles. A hacky bash
solution to scrape every 10 minues (with massive drift) is:

```bash
$ ( while true; do echo asdf; sleep 5; done ) &>news3k.log & \
    echo $! >news3k.pid ; disown
```

The file `news3k.log` now contains the scraping logs and `news3k.pid` contains
the pid of the background process.
In order to stop scraping, execute `$ kill $(< news3k.pid)`.

# License

This project uses the MIT License. Dependency licensing:

- `newspaper3k` -  MIT
- `flask` - BSD
- `click` - BSD
- `iso8601` - MIT
