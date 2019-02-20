#!/usr/bin/env python

import os
import sqlite3
import datetime
import struct
from base64 import b64encode, b64decode

from flask import Flask, g, request, render_template, Blueprint

import sys
if sys.version_info[0] < 3: raise Exception("Must use python 3")

fromiso = None
if sys.version_info[0] == 3 and sys.version_info[1] < 7:
    import iso8601
    fromiso = iso8601.parse_date
else:
    fromiso = datetime.datetime.fromisoformat
	

# b64 encode/decode i64 values
# automatic padding/unpadding
def i64enc(s): return b64encode(struct.pack("Q", s), b'-_').decode('utf-8')[:-1]
def i64dec(s): return struct.unpack("Q", b64decode(s + '=', b'-_'))[0]
def split(s): return s.split('\n')
def fmtdate(s, fmt = None):
    if type(s) is str:
        d = fromiso(s)
    else:
        d = s
    today = datetime.datetime.today()
    if fmt != None:
        return d.strftime(fmt)
    elif d.year == today.year and d.month == today.month \
            and d.day == today.day:
        return d.strftime('Today %H:%M')
    elif d.year == today.year:
        return d.strftime('%d %b %H:%M')
    else:
        return d.strftime('%d %b %Y %H:%HM')

app = Flask(__name__)
app.config.from_object(__name__)

app.config['DATABASE'] = "news.sqlite"
app.config['PERPAGE'] = 250
app.jinja_env.auto_reload = True 

app.jinja_env.globals.update(
    b64enc = i64enc,
    b64dec = i64dec,
    split = split,
    fmtdate = fmtdate,
)

def db():
    if 'db' not in g:
        g.db = sqlite3.connect(app.config['DATABASE'])
                #detect_types = sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.before_request
def before_request():
    if 'localhost' in request.host_url or '0.0.0.0' in request.host_url:
        app.jinja_env.cache = {}

@app.route("/article")
def article():
    handle = request.args.get('handle')
    article = None
    if handle != None:
        handleDec = i64dec(handle)
        article = db().execute('SELECT a.url, a.handle, a.title, '
                'a.found_at, a.text, s.url AS srcurl, s.brand '
                'FROM articles AS a '
                'LEFT JOIN sources AS s ON a.source = s.id '
                'WHERE a.handle = ? '
                'LIMIT 1;', (handleDec,)).fetchone()

    return render_template('article.html', article = article)

@app.route("/")
@app.route("/index")
def index():
    before = request.args.get('before')
    #if before == None: before = datetime.datetime.now()
    after = request.args.get('after')

    perpage = app.config['PERPAGE']
    now = datetime.datetime.now()

    articles = db().execute('SELECT a.url, a.handle, a.title, '
            'a.summary, a.found_at, s.url AS srcurl, s.brand '
            'FROM articles AS a '
            'LEFT JOIN sources AS s ON a.source = s.id '
            'WHERE title IS NOT NULL '
            'ORDER BY a.found_at, a.handle DESC LIMIT ?;',
            (perpage,)).fetchall()

    return render_template('index.html',
            articles = articles[:perpage],
            generated = now)
