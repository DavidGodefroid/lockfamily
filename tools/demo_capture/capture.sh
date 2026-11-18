#!/bin/bash
# How the captures of this directory were made (2026-11-18, Linux, Docker):
# a throwaway Postgres, one locksql lock added with `lox add`, `lox run` in a
# 76-column tmux window, the agent's MCP calls sent by mcp_call.py, and
# `tmux capture-pane -e` after each step. tools/demo_svg.py draws the demo
# from the result. Assembled from the commands of that run; the names it
# creates (demo61-*, ~/projects/shop) must be free. Needs lox, locksql,
# docker, tmux, jq, python3 and script(1).
#
#   bash tools/demo_capture/capture.sh OUT_DIR
set -eu
OUT=$(mkdir -p "$1" && cd "$1" && pwd)
D=$(cd "$(dirname "$0")" && pwd)
export WS=$HOME/projects/shop
export XDG_RUNTIME_DIR=$HOME/.demo61-run   # a facade socket of its own, away from any other lox run
TS=demo61
PW=demo-pw-61                               # the throwaway database's password, typed in lox run only

# 1. A fake shop database.
docker network create --subnet 10.251.61.0/24 demo61-net >/dev/null
docker run -d --name demo61-pg --network demo61-net -p 5434:5432 -e POSTGRES_PASSWORD=adminpw postgres:17 >/dev/null
until docker exec demo61-pg pg_isready -U postgres >/dev/null 2>&1; do sleep 1; done
sleep 2
pg() { docker exec -i -e PGPASSWORD=adminpw demo61-pg psql -q -v ON_ERROR_STOP=1 -U postgres "$@"; }
pg -c "CREATE DATABASE shop"
pg -d shop <<'SQL'
CREATE ROLE agent LOGIN PASSWORD 'demo-pw-61';
CREATE TABLE customers (id int PRIMARY KEY, name text, email text, phone text, city text);
INSERT INTO customers VALUES
 (311,'Alice Dupont','alice@example.com','+32 470 12 34 56','Namur'),
 (312,'Bob Martin','bob@example.com','+32 471 98 76 54','Liège'),
 (313,'Chloé Lambert','chloe@example.org','+32 472 11 22 33','Bruxelles');
CREATE TABLE orders (id int PRIMARY KEY, customer_id int REFERENCES customers, total numeric(10,2), status text, created date);
INSERT INTO orders VALUES
 (4810,311,129.00,'paid','2026-11-12'),
 (4811,312,54.50,'paid','2026-11-13'),
 (4812,313,89.90,'pending','2026-11-14'),
 (4813,311,24.00,'shipped','2026-11-15');
GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO agent;
SQL

# 2. The lock: lox add, then the write tier in the profile.
mkdir -p "$WS" && chmod 0755 "$WS" && mkdir -p -m 0700 "$XDG_RUNTIME_DIR" && cd "$WS" && git init -q
lox add locksql --non-interactive --name shop --engine postgres --host host.docker.internal --port 5434 \
	--database shop --user agent --credentials ask --tls disable </dev/null
printf 'tier = "write"\n' >>.locksql/config.toml
# The agent's client runs the image lox add pinned, so both ends are the same release.
LOCKSQL_IMAGE=$(awk '/locksql@sha256/ { print $2 }' .lockfamily/lockfamily.yaml)
export LOCKSQL_IMAGE

# 3. lox run, in a terminal of its own; the console's start questions are answered there.
tmux new-session -d -s $TS -n run -x 76 -y 24 -c "$WS" -e XDG_RUNTIME_DIR="$XDG_RUNTIME_DIR" "sh -c 'lox run; exec sleep 99999'"
pane() { tmux capture-pane -t $TS:run -p; }
waitfor() { until pane | grep -qE "$1"; do sleep 1; done; }
snap() { sleep "${2:-3}"; tmux capture-pane -t $TS:run -p -e >"$OUT/lox-run-$1.ansi"; }
waitfor 'Apply\? \[y/N\]' && tmux send-keys -t $TS:run y Enter
waitfor ' AUTO ' && tmux resize-window -t $TS:run -x 76 -y 24
waitfor 'Apply these changes' && sleep 3 && tmux send-keys -t $TS:run y
waitfor '│ Password for' && sleep 3 && tmux send-keys -t $TS:run "$PW" Enter
waitfor '│ Accept all' && sleep 3 && tmux send-keys -t $TS:run a Enter
sleep 6
snap s0 0

# 4. The agent's four calls, then the fifth with the decided ticket.
call() { python3 "$D/mcp_call.py" "$1" "$2" | grep -v '^STRUCTURED: '; }
Q1="SELECT o.id, c.name, c.email, o.total, o.status FROM orders o JOIN customers c ON c.id = o.customer_id WHERE o.status = 'pending' LIMIT 10"
Q2="UPDATE orders SET status = 'refunded' WHERE id = 4812"
call locksql_plan "$(jq -cn --arg s "$Q1" '{sql:$s}')" >"$OUT/agent-a1-plan.txt"
id=$(awk '/^plan_id/ { print $2 }' "$OUT/agent-a1-plan.txt")
call locksql_run "{\"plan_id\":\"$id\"}" >"$OUT/agent-a2-run.txt"
snap s1
call locksql_plan "$(jq -cn --arg s "$Q2" '{sql:$s}')" >"$OUT/agent-a3-plan.txt"
id=$(awk '/^plan_id/ { print $2 }' "$OUT/agent-a3-plan.txt")
call locksql_run "{\"plan_id\":\"$id\"}" >"$OUT/agent-a4-pending.txt"
snap s2
ticket=$(grep -o 'ticket [0-9A-Z]*' "$OUT/agent-a4-pending.txt" | head -n 1 | cut -d' ' -f2)
tmux send-keys -t $TS:run y # the approval
snap s3 4
call locksql_run "{\"plan_id\":\"$id\",\"ticket\":\"$ticket\"}" >"$OUT/agent-a5-done.txt"
snap s4

# 5. lox audit, and the releases that ran.
script -qec "stty cols 100; lox audit --no-pager" /dev/null | tr -d '\r' >"$OUT/lox-audit.ansi"
{ lox --version && grep image: .lockfamily/lockfamily.yaml; } >"$OUT/versions.txt"

# 6. Remove everything this script started.
tmux send-keys -t $TS:run q && sleep 1 && tmux send-keys -t $TS:run q && sleep 4
P=$(jq -r .project .lockfamily/up.json)
S=${XDG_STATE_HOME:-$HOME/.local/state}/lockfamily/$P
docker compose -p "$P" --project-directory "$S" -f "$S/compose.yaml" down -v --remove-orphans
rm -f "${XDG_STATE_HOME:-$HOME/.local/state}/lockfamily/facades/locks.d/$P.json"
cd / && rm -rf "$S" "$WS" "$XDG_RUNTIME_DIR"
tmux kill-session -t $TS
docker rm -f demo61-pg >/dev/null && docker network rm demo61-net >/dev/null
