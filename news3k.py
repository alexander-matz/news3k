#!/usr/bin/env python

import sys
import newspaper
from pprint import pprint
import datetime
import traceback
import os

import warnings
import sqlite3

import random

db_name = os.environ.get("NEWS3K_DATABASE", "news.sqlite")

with warnings.catch_warnings():
    warnings.filterwarnings("ignore",category=DeprecationWarning)
    import nltk
    nltk.data.path.append('./nltk_data')

def article_handle(cur, trys):
    for _ in range(trys):
        candidate = random.getrandbits(63)
        res = cur.execute("SELECT 1 FROM articles WHERE handle = ? LIMIT 1;", (candidate,))
        if res.fetchone() == None: return candidate
    return None

def fetch_article(article, handle, src_id, found_at, db):
    article.download()
    article.parse()
    article.nlp()
    db.execute("INSERT OR IGNORE INTO articles "
        "(url, handle, source, title, top_img, text, summary, found_at)"
        "VALUES(?, ?, ?, ?, ?, ?, ?, ?);",
        (article.url, handle, src_id, article.title, article.top_image,
        article.text, article.summary, found_at))
    db.commit()
    return True

def block_article(article, handle, src_id, found_at, db):
    db.execute("INSERT OR IGNORE INTO articles (url, handle, source, found_at) "
            "VALUES(?, ?, ?, ?);", (article.url, handle, src_id, found_at))
    db.commit()
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: news3k urls")
        sys.exit(1)

    db = sqlite3.connect(db_name)
    db.execute("CREATE TABLE IF NOT EXISTS sources "
             "(id INTEGER PRIMARY KEY, url TEXT UNIQUE, domain TEXT, brand TEXT);")
    db.execute("CREATE TABLE IF NOT EXISTS articles "
             "(url PRIMARY KEY, handle INTEGER, source INTEGER, "
             " title TEXT, top_img TEXT, text TEXT, summary TEXT, found_at DATE, "
             " FOREIGN KEY (source) REFERENCES sources(id) ON DELETE CASCADE);")
    db.execute("CREATE INDEX IF NOT EXISTS a_fh ON articles(found_at, handle);")
    cur = db.cursor()
    #db.set_trace_callback(print)

    found_at = datetime.datetime.now()

    for link in sys.argv[1:]:
        print('collecting: %s' % (link,))
        try:
            src = newspaper.build(link, memoize_articles = False)
            src_id = cur.execute("SELECT id FROM sources WHERE url = ?;", (link,)).fetchone()
            src_is_new = False
            if src_id == None:
                cur.execute("INSERT INTO sources(url, domain, brand) VALUES(?, ?, ?);",
                    (src.url, src.domain, src.brand))
                src_id = cur.lastrowid
                db.commit()
                src_is_new = True
            else:
                src_id = src_id[0]
            print('total articles: %d' % (len(src.articles),))

            n = 0
            for article in src.articles:
                if cur.execute("SELECT 1 FROM articles WHERE url = ? LIMIT 1;",
                        (article.url,)).fetchone() != None:
                    continue

                handle = article_handle(db, 10)
                if handle == None:
                    print('unable to generate article handle! database crowded?')
                    continue

                if not src_is_new:
                    if fetch_article(article, handle, src_id, found_at, db):
                        n += 1
                else:
                    if block_article(article, handle, src_id, found_at, db):
                        n += 1
            print('new articles: %d' % n)
        except Exception as e:
            traceback.print_exception(e)
    db.close()

    sys.exit(0)
