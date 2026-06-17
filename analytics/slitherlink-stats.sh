#!/usr/bin/env bash
# Relatório de acessos do slitherlink. Uso: slitherlink-stats.sh
exec /root/slitherlink-analytics/venv/bin/python /root/slitherlink-analytics/report.py "$@"
