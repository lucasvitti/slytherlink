#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Relatório de acessos do slitherlink (lê stats.db gerado por collect.py).

Imprime: total de page-views e visitantes únicos, hoje, últimos 7 dias,
top países, divisão por device/OS/navegador e os últimos 14 dias. Só stdlib.
"""
import os
import sqlite3
import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, 'stats.db')


def main():
    if not os.path.exists(DB):
        print('sem dados ainda (stats.db não existe — rode collect.py)')
        return
    con = sqlite3.connect(DB)
    q = lambda sql, *a: con.execute(sql, a).fetchall()

    hoje = datetime.date.today()
    d7 = (hoje - datetime.timedelta(days=6)).isoformat()
    h = hoje.isoformat()

    tot = q('SELECT COUNT(*), COUNT(DISTINCT visitor) FROM hits')[0]
    hj = q('SELECT COUNT(*), COUNT(DISTINCT visitor) FROM hits WHERE day=?', h)[0]
    s7 = q('SELECT COUNT(*), COUNT(DISTINCT visitor) FROM hits WHERE day>=?', d7)[0]

    print('=' * 52)
    print(' Slitherlink — acessos (slitherlink.lucas.mat.br)')
    print('=' * 52)
    print(' Total .......... %6d views | %5d visitantes' % (tot[0], tot[1] or 0))
    print(' Hoje ........... %6d views | %5d visitantes' % (hj[0], hj[1] or 0))
    print(' Últimos 7 dias . %6d views | %5d visitantes' % (s7[0], s7[1] or 0))

    def secao(titulo, sql):
        rs = q(sql)
        if not rs:
            return
        print('\n %s' % titulo)
        largura = max((len(str(r[0])) for r in rs), default=1)
        topo = max((r[1] for r in rs), default=1) or 1
        for nome, n in rs:
            barra = '#' * int(round(20 * n / topo))
            print('   %-*s %5d  %s' % (largura, nome, n, barra))

    secao('Top países (views)',
          'SELECT country, COUNT(*) c FROM hits GROUP BY country ORDER BY c DESC LIMIT 10')
    secao('Device', 'SELECT device, COUNT(*) c FROM hits GROUP BY device ORDER BY c DESC')
    secao('Sistema', 'SELECT os, COUNT(*) c FROM hits GROUP BY os ORDER BY c DESC')
    secao('Navegador', 'SELECT browser, COUNT(*) c FROM hits GROUP BY browser ORDER BY c DESC')

    print('\n Últimos 14 dias (views | únicos)')
    by = {d: (v, u) for d, v, u in q(
        'SELECT day, COUNT(*), COUNT(DISTINCT visitor) FROM hits GROUP BY day')}
    for i in range(13, -1, -1):
        d = (hoje - datetime.timedelta(days=i)).isoformat()
        v, u = by.get(d, (0, 0))
        print('   %s  %4d | %4d  %s' % (d, v, u, '#' * min(40, v)))
    con.close()


if __name__ == '__main__':
    main()
