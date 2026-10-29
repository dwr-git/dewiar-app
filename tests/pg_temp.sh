#!/bin/bash
# Временный PostgreSQL для проверок базы, если своего нет (29.10: без него 10 проверок молча «пропускались» — и пропустили,
# что счёт сайта в программах с 25.10 показывался как «заряд %»). Подключать: source tests/pg_temp.sh — ставит
# DEWIAR_TEST_PG и при выходе останавливает базу. Есть рабочий DEWIAR_TEST_PG или нет initdb — ничего не делает.
_pg_url() { local h p d u w; IFS=: read -r h p d u w <<<"$1"; echo "postgresql://$u:$w@$h:$p/$d"; }
if ! psql "$(_pg_url "${DEWIAR_TEST_PG:-127.0.0.1:5432:dwsite:dwtest:pgpass}")" -c 'select 1' >/dev/null 2>&1; then
  _PGBIN=$(ls -d /usr/lib/postgresql/*/bin 2>/dev/null | sort -V | tail -1)
  if [ -x "$_PGBIN/initdb" ]; then
    _PGDIR=$(mktemp -d /var/tmp/dwpg.XXXXXX); _PGPORT=$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])')
    _AS=""; [ "$(id -u)" = 0 ] && { chown postgres "$_PGDIR"; _AS="su postgres -c"; }
    _CMD="$_PGBIN/initdb -D $_PGDIR/d -A trust -U postgres >/dev/null && $_PGBIN/pg_ctl -D $_PGDIR/d -o '-p $_PGPORT -k $_PGDIR' -l $_PGDIR/log -w start >/dev/null"
    if (cd /tmp && if [ -n "$_AS" ]; then $_AS "$_CMD"; else bash -c "$_CMD"; fi) && \
       psql "postgresql://postgres@127.0.0.1:$_PGPORT/postgres" -q -c "create user dwtest password 'pgpass' superuser" -c "create database dwsite owner dwtest" >/dev/null 2>&1; then
      export DEWIAR_TEST_PG="127.0.0.1:$_PGPORT:dwsite:dwtest:pgpass"
      _pg_stop() { (cd /tmp && if [ -n "$_AS" ]; then $_AS "$_PGBIN/pg_ctl -D $_PGDIR/d -m fast stop" ; else "$_PGBIN/pg_ctl" -D "$_PGDIR/d" -m fast stop; fi) >/dev/null 2>&1; rm -rf "$_PGDIR"; }
      echo "PostgreSQL для проверок — временный, порт $_PGPORT"
    else
      rm -rf "$_PGDIR"
    fi
  fi
fi
