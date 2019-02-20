#!/usr/bin/env python

import sys
import newspaper
from pprint import pprint
import datetime
import traceback
import os

import warnings
import sqlite3
import nltk

import random

nltk.data.path.append("./nltk_data")
db_name = os.environ.get("NEWS3K_DATABASE", "news.sqlite")

def article_handle(cur, trys):
    for _ in range(trys):
        candidate = random.getrandbits(63)
        res = cur.execute("SELECT 1 FROM articles WHERE handle = ? LIMIT 1;", (candidate,))
        if res.fetchone() == None: return candidate
    return None

def fetch_article(article, handle, src_id, found_at, db):
    try:
        article.download()
        article.parse()
        article.nlp()
    except Exception as e:
        traceback.print_exc()
        return False
    db.execute("INSERT OR IGNORE INTO articles "
        "(url, handle, source, title, top_img, text, summary, found_at)"
        "VALUES(?, ?, ?, ?, ?, ?, ?, ?);",
        (article.url, handle, src_id, article.title, article.top_image,
        article.text, article.summary, found_at))
    return True

def block_article(article, handle, src_id, found_at, db):
    db.execute("INSERT OR IGNORE INTO articles (url, handle, source, found_at) "
            "VALUES(?, ?, ?, ?);", (article.url, handle, src_id, found_at))
    return True

if __name__ == "__main__":
    db = sqlite3.connect(db_name)
    db.execute("CREATE TABLE IF NOT EXISTS sources"
             "(id INTEGER PRIMARY KEY, url TEXT UNIQUE NOT NULL, domain TEXT, brand TEXT);")
    db.execute("CREATE TABLE IF NOT EXISTS articles "
            "(url PRIMARY KEY, handle INTEGER NOT NULL, source INTEGER NOT NULL, "
             " title TEXT, top_img TEXT, text TEXT, summary TEXT, found_at DATE, "
             " FOREIGN KEY (source) REFERENCES sources(id) ON DELETE CASCADE);")
    db.execute("CREATE INDEX IF NOT EXISTS a_fh ON articles(found_at, handle);")
    cur = db.cursor()
    #db.set_trace_callback(print)

    found_at = datetime.datetime.now()

    nsources = 0
    sources = cur.execute("SELECT id, url, domain, brand FROM sources;").fetchall()
    for (src_id, url, domain, brand) in sources:
        nsources += 1
        print("collecting: %s" % (url,))
        try:
            src = newspaper.build(url, memoize_articles = False)
        except Exception as e:
            traceback.print_exc()
            continue
        src_is_new = False
        if domain == None or brand == None:
            db.execute("UPDATE sources SET domain = ?, brand = ? WHERE id = ?",
                    (src.domain, src.brand, src_id))
            db.commit()
            src_is_new = True

        new = 0
        blocked = 0
        for article in src.articles:
            if cur.execute("SELECT 1 FROM articles WHERE url = ? LIMIT 1;",
                    (article.url,)).fetchone() != None:
                continue

            handle = article_handle(db, 10)
            if handle == None:
                print("unable to generate article handle! database crowded?")
                continue

            if not src_is_new:
                if fetch_article(article, handle, src_id, found_at, db):
                    new += 1
            else:
                if block_article(article, handle, src_id, found_at, db):
                    blocked+= 1
        db.commit()
        print("total: %d, new %d, blocked: %d" % (len(src.articles), new, blocked))

    if nsources == 0:
        print("no sources found in 'sources' table, add IDs and URLs")
    db.close()

    sys.exit(0)
