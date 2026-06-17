# Slitherlink — contagem de acessos (server-side)

Analytics de **page-views** do site `slitherlink.lucas.mat.br`, a partir dos
logs do nginx. Sem alterar o site, **sem endpoint público novo**, e **sem
guardar IP** (só país derivado + um hash diário salgado para contar únicos).

## Como funciona
- `collect.py` — lê `/var/log/nginx/slitherlink.access.log*` (atual + rotacionados,
  inclusive `.gz`), mantém só os **carregamentos do documento** (`GET /` ou
  `/index.html`, status 200/304, sem bots/headless), resolve **país** (DB-IP,
  offline) e **device/OS/navegador** (User-Agent), e grava em `stats.db` (SQLite).
  Idempotente (`INSERT OR IGNORE` por hash da linha): rodar de novo ou rotacionar
  logs nunca duplica.
- `report.py` — imprime totais, hoje, últimos 7/14 dias, top países e divisão por
  device/OS/navegador.

## No VPS (Hostinger, alias `vps`)
```
/root/slitherlink-analytics/
  collect.py  report.py  slitherlink-stats.sh
  venv/                  # python + maxminddb
  dbip-country.mmdb      # DB-IP Country Lite (offline; ~8 MB)
  salt                   # segredo do hash diário (0600, NÃO versionar)
  stats.db               # o banco
  collect.log            # saída do cron
```
- **Ver o relatório:** `slitherlink-stats` (wrapper em `/usr/local/bin`).
- **Cron:** a cada 15 min → `*/15 * * * * .../venv/bin/python .../collect.py`.

## Manutenção
- **GeoIP mensal (opcional):** o DB-IP atualiza todo mês. Para refrescar:
  ```
  cd /root/slitherlink-analytics
  curl -fsSL "https://download.db-ip.com/free/dbip-country-lite-$(date +%Y-%m).mmdb.gz" -o d.gz \
    && gunzip -f d.gz && mv -f d dbip-country.mmdb
  ```
  (Funciona sem o arquivo do mês: países só ficam um pouco menos precisos.)
- **Privacidade:** o IP é usado em memória para país + hash e descartado; o banco
  guarda apenas `country, device, os, browser, path, visitor(hash diário)`.

## Deploy / atualização dos scripts
Editar aqui e copiar: `scp analytics/collect.py analytics/report.py vps:/root/slitherlink-analytics/`.
