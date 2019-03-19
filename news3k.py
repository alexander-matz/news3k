#!/usr/bin/env python

# vim: ts=4 sts=4 sw=4 et ai

import sys
assert sys.version_info >= (3, 4)

import newspaper
from pprint import pprint
import datetime
import traceback
import os
import click
from urllib.parse import urlparse, ParseResult

import warnings
import sqlite3
import nltk

import random


nltk.data.path.append("./nltk_data")

def article_handle(db, trys):
    for _ in range(trys):
        candidate = random.getrandbits(63)
        res = db.execute("SELECT 1 FROM articles WHERE handle = ? LIMIT 1;", (candidate,))
        if res.fetchone() == None: return candidate
    return None

def build_source(url):
    try:
        src = newspaper.build(url, memoize_articles = False)
    except Exception as e:
        print(e)
        return None
    return src

def article_exists(db, url):
    parsed = urlparse(url)
    noprefix = ParseResult("", *parsed[1:]).geturl()
    res = db.execute("SELECT 1 FROM articles WHERE url LIKE '%' || ? LIMIT 1;", (noprefix,))
    return res.fetchone() != None

def fetch_single(article, src_id, found_at, db, dummy = False):
    handle = article_handle(db, 10)
    if handle == None:
        print("unable to generate article handle. database crowded?")
        return False

    title, top_img, text, summary = None, None, None, None
    if not dummy:
        try:
            article.download()
            article.parse()
            article.nlp()
        except Exception as e:
            print(e)
            return False
        title = article.title
        top_img = article.top_image
        text = article.text
        summary = article.summary

    db.execute("INSERT OR IGNORE INTO articles "
        "(url, handle, source, title, top_img, text, summary, found_at)"
        "VALUES(?, ?, ?, ?, ?, ?, ?, ?);",
        (article.url, handle, src_id, title, top_img,
        text, summary, found_at))
    return True

@click.group()
@click.option("--database", default="news.sqlite")
@click.option("--debug/--no-debug", default=False)
@click.pass_context
def cli(ctx, database, debug):
    db = sqlite3.connect(database)
    db.execute("CREATE TABLE IF NOT EXISTS sources"
             "(id INTEGER PRIMARY KEY, url TEXT UNIQUE NOT NULL, domain TEXT, brand TEXT);")
    db.execute("CREATE TABLE IF NOT EXISTS articles "
             "(url PRIMARY KEY, handle INTEGER NOT NULL, source INTEGER NOT NULL, "
             " title TEXT, top_img TEXT, text TEXT, summary TEXT, found_at DATE, "
             " FOREIGN KEY (source) REFERENCES sources(id) ON DELETE CASCADE);")
    db.execute("CREATE INDEX IF NOT EXISTS a_found ON articles(found_at);")
    db.execute("CREATE INDEX IF NOT EXISTS a_handle ON articles(handle);")

    # wrapper function voids syntax error in python 2.x
    if debug:
        def cb(s): print(s) 
        db.set_trace_callback(cb)
    ctx.obj["DB"] = db
    ctx.obj["DEBUG"] = debug
    pass

@cli.command()
@click.pass_context
def clean(ctx):
    db = ctx.obj["DB"]
    db.executescript("""
        DELETE FROM articles WHERE found_at < date('now', '-14 days');
        VACUUM;
    """)

@cli.command()
@click.pass_context
def fetch_articles(ctx):
    db = ctx.obj["DB"]
    found_at = datetime.datetime.now()
    nsources = 0
    sources = db.execute("SELECT id, url, domain, brand FROM sources;").fetchall()
    for (src_id, url, domain, brand) in sources:
        if domain == None or brand == None:
            print('source %s not initialized' % (url))
            return

        nsources += 1
        print("collecting: %s" % (url,))

        src = build_source(url)
        if src == None:
            return

        new, failed = 0, 0
        for article in src.articles:
            if article_exists(db, article.url):
                continue

            if fetch_single(article, src_id, found_at, db):
                new += 1
            else:
                failed += 1

        db.commit()
        print("total: %d, new: %d, failed: %d" % (len(src.articles), new, failed))

    if nsources == 0:
        print("no sources found in 'sources' table, add IDs and URLs")

@cli.command()
@click.argument('url')
@click.option('--nposts', default=10)
@click.pass_context
def add_source(ctx, url, nposts):
    db = ctx.obj["DB"]
    if db.execute("SELECT 1 FROM sources WHERE url = ? LIMIT 1;",
            (url,)).fetchone() != None:
        print('url already added!')
        return

    src = build_source(url)
    if src == None:
        return

    cur = db.cursor()
    cur.execute("INSERT INTO sources (url, domain, brand) "
                "VALUES(?, ?, ?);", (url, src.domain, src.brand))
    src_id = cur.lastrowid
    cur.close()
    found_at = datetime.datetime.now()
    total, new, blocked, failed = len(src.articles), 0, 0, 0
    for article in src.articles:
        if article_exists(db, article.url):
            continue
        
        if new < nposts:
            if fetch_single(article, src_id, found_at, db):
                new += 1
            else:
                failed += 1
        else:
            fetch_single(article, src_id, found_at, db, True)
            blocked += 1
    db.commit()
    print("total: %d, new: %d, blocked: %d failed: %d" % (total, new, blocked, failed))

@cli.command()
@click.argument('url')
@click.pass_context
def delete_source(ctx, url):
    db = ctx.obj["DB"]
    src_id = db.execute("SELECT id FROM sources WHERE url = ?;", (url,)).fetchone()
    if src_id == 0:
        print('source url not found in database')
        return
    src_id = src_id[0]
    db.execute("DELETE FROM sources WHERE id = ?;", (src_id,))
    db.execute("DELETE FROM articles WHERE source = ?;", (src_id,))
    db.commit()
    print('deleted source %s' % (url,))

@cli.command()
@click.pass_context
def list_sources(ctx):
    db = ctx.obj["DB"]
    for (url, brand, domain) in db.execute("SELECT url, brand, domain FROM sources;"):
        print("%s, %s @ %s" % (brand, domain, url))

if __name__ == "__main__":
    cli(obj = {})
