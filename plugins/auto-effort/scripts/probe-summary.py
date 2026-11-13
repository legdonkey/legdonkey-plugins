import json, sys
for line in open(sys.argv[1]):
    r = json.loads(line)
    if r["kind"] == "request":
        print(f"  REQ  t{r['turn']} n={r.get('messageCount')} top={r.get('topEffort')} perMsg={r.get('perMessageEffort')}")
    else:
        u = r.get("usage") or {}
        print(f"  STEP t{r['turn']}.{r['index']} engine={r['engineEffort']} -> {r['rewrittenTo']} read={u.get('cache_read_input_tokens')} write={u.get('cache_creation_input_tokens')} in={u.get('input_tokens')} out={u.get('output_tokens')} stop={r.get('stopReason')}")
