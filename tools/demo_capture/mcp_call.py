#!/usr/bin/env python3
"""mcp_call.py TOOL [JSON-ARGUMENTS]: one MCP tools/call sent to `locksql mcp`, as an agent's harness sends it.

Prints the text the agent gets back. WS, XDG_RUNTIME_DIR and LOCKSQL_IMAGE come from capture.sh.
"""
import json, os, subprocess, sys
p = subprocess.Popen(["locksql", "mcp"], cwd=os.environ["WS"],
                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
def rpc(i, method, params=None, notify=False):
    m = {"jsonrpc": "2.0", "method": method}
    if params is not None: m["params"] = params
    if not notify: m["id"] = i
    p.stdin.write(json.dumps(m) + "\n"); p.stdin.flush()
    if notify: return
    while True:
        line = p.stdout.readline()
        if not line: sys.exit("server closed")
        r = json.loads(line)
        if r.get("id") == i: return r
r = rpc(1, "initialize", {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "demo61", "version": "0"}})
if sys.argv[1] == "init": print(json.dumps(r, indent=1))
rpc(0, "notifications/initialized", notify=True)
if sys.argv[1] == "list":
    for t in rpc(2, "tools/list")["result"]["tools"]: print(t["name"], json.dumps(t["inputSchema"].get("properties", {}))[:300])
elif sys.argv[1] != "init":
    r = rpc(3, "tools/call", {"name": sys.argv[1], "arguments": json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}})
    res = r.get("result", r)
    for c in res.get("content", []): print(c.get("text", c))
    if res.get("isError"): print("[isError]")
    if "structuredContent" in res: print("STRUCTURED:", json.dumps(res["structuredContent"]))
p.stdin.close(); p.wait(timeout=20)
