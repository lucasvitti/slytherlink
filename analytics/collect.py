#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Coletor de acessos do slitherlink.lucas.mat.br.

Lê os logs do nginx (atual + rotacionados), conta apenas PAGE VIEWS do
documento (GET / ou /index.html, 200/304, sem bots), resolve o país (DB-IP,
offline) e o device a partir do User-Agent, e grava em SQLite.

PRIVACIDADE: o IP NUNCA é guardado — só o país derivado e um hash diário
salgado (permite contar visitantes únicos por dia sem reter o IP). Idempotente
(INSERT OR IGNORE por hash da linha), então rodar de novo / rotacionar logs
não duplica nada.
"""
import os
import re
import gzip
import glob
import sqlite3
import hashlib
import datetime
import maxminddb

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, 'stats.db')
MMDB = os.path.join(BASE, 'dbip-country.mmdb')
SALT_FILE = os.path.join(BASE, 'salt')
LOG_GLOB = '/var/log/nginx/slitherlink.access.log*'

LINE_RE = re.compile(
    r'^(\S+) \S+ \S+ \[([^\]]+)\] "(\S+) (\S+) [^"]*" (\d{3}) \S+ "[^"]*" "([^"]*)"')
BOTS = ('bot', 'crawl', 'spider', 'slurp', 'headless', 'monitor', 'uptime',
        'pingdom', 'curl', 'wget', 'python-requests', 'go-http', 'facebookexternalhit',
        'whatsapp', 'twitterbot', 'slackbot', 'telegrambot', 'discordbot', 'embedly',
        'lighthouse', 'ahrefs', 'semrush', 'bingpreview', 'dataprovider', 'preview', 'scrapy')


def get_salt():
    """Segredo fixo (gerado uma vez) que entra no hash diário do visitante."""
    if os.path.exists(SALT_FILE):
        with open(SALT_FILE, 'rb') as f:
            return f.read()
    s = os.urandom(16)
    fd = os.open(SALT_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.write(fd, s)
    os.close(fd)
    return s


def parse_ua(ua):
    """(device, os, browser) por heurística simples sobre o User-Agent."""
    u = ua.lower()
    if 'ipad' in u or 'tablet' in u or ('android' in u and 'mobile' not in u):
        dev = 'tablet'
    elif 'mobi' in u or 'iphone' in u or 'ipod' in u:
        dev = 'mobile'
    else:
        dev = 'desktop'
    if 'windows' in u:
        osf = 'Windows'
    elif 'iphone' in u or 'ipad' in u or 'cpu os' in u or ' ios' in u:
        osf = 'iOS'
    elif 'mac os' in u or 'macintosh' in u:
        osf = 'macOS'
    elif 'android' in u:
        osf = 'Android'
    elif 'linux' in u:
        osf = 'Linux'
    else:
        osf = 'outro'
    if 'edg' in u:
        br = 'Edge'
    elif 'opr' in u or 'opera' in u:
        br = 'Opera'
    elif 'samsungbrowser' in u:
        br = 'Samsung'
    elif 'firefox' in u or 'fxios' in u:
        br = 'Firefox'
    elif 'chrome' in u or 'crios' in u:
        br = 'Chrome'
    elif 'safari' in u:
        br = 'Safari'
    else:
        br = 'outro'
    return dev, osf, br


def opener(path):
    if path.endswith('.gz'):
        return gzip.open(path, 'rt', errors='replace')
    return open(path, 'rt', errors='replace')


def main():
    salt = get_salt()
    geo = maxminddb.open_database(MMDB)
    con = sqlite3.connect(DB)
    con.execute('''CREATE TABLE IF NOT EXISTS hits(
        lineid TEXT PRIMARY KEY, ts TEXT, day TEXT, country TEXT,
        device TEXT, os TEXT, browser TEXT, path TEXT, visitor TEXT)''')
    con.execute('CREATE INDEX IF NOT EXISTS idx_day ON hits(day)')

    inseridos = 0
    for path in sorted(glob.glob(LOG_GLOB)):
        try:
            f = opener(path)
        except OSError:
            continue
        with f:
            for line in f:
                m = LINE_RE.match(line)
                if not m:
                    continue
                ip, tstr, method, rawpath, status, ua = m.groups()
                if method != 'GET' or status not in ('200', '304'):
                    continue
                if rawpath.split('?', 1)[0] not in ('/', '/index.html'):
                    continue
                ual = ua.lower()
                if any(b in ual for b in BOTS):
                    continue
                try:
                    dt = datetime.datetime.strptime(tstr, '%d/%b/%Y:%H:%M:%S %z')
                except ValueError:
                    continue
                day = dt.strftime('%Y-%m-%d')
                lineid = hashlib.sha256(line.encode('utf-8', 'replace')).hexdigest()[:24]
                try:
                    rec = geo.get(ip)
                except Exception:
                    rec = None
                country = ((rec or {}).get('country') or {}).get('iso_code') or '??'
                dev, osf, br = parse_ua(ua)
                visitor = hashlib.sha256(salt + day.encode() + ip.encode()).hexdigest()[:16]
                cur = con.execute(
                    'INSERT OR IGNORE INTO hits VALUES(?,?,?,?,?,?,?,?,?)',
                    (lineid, dt.isoformat(), day, country, dev, osf, br,
                     rawpath.split('?', 1)[0], visitor))
                inseridos += cur.rowcount
    con.commit()
    con.close()
    geo.close()
    print('inseridos %d novos page-views; db=%s' % (inseridos, DB))


if __name__ == '__main__':
    main()
