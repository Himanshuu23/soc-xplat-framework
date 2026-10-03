#!/bin/sh
sim=$1
bindir=$2
shift 2

pass=0
fail=0
printf '%-14s %-6s %8s  %s\n' TEST RESULT CYCLES NOTE
printf '%-14s %-6s %8s  %s\n' -------------- ------ -------- ----

for t in "$@"; do
    out=$("$sim" "$bindir/$t.bin" 2>&1)
    rc=$?
    cycles=$(printf '%s\n' "$out" | sed -n 's/.*after \([0-9]*\) cycles.*/\1/p' | tail -n 1)
    note=""
    if [ "$rc" -eq 0 ] && printf '%s\n' "$out" | grep -q "^PASS $t\$"; then
        result=PASS
        pass=$((pass + 1))
    else
        result=FAIL
        fail=$((fail + 1))
        note="exit code $rc"
        printf '%s\n' "$out" | sed 's/^/    | /'
    fi
    printf '%-14s %-6s %8s  %s\n' "$t" "$result" "${cycles:--}" "$note"
done

if [ -n "$REGTOOL" ]; then
    out=$($REGTOOL 2>&1)
    rc=$?
    if [ "$rc" -eq 0 ]; then
        result=PASS
        pass=$((pass + 1))
    else
        result=FAIL
        fail=$((fail + 1))
        printf '%s\n' "$out" | sed 's/^/    | /'
    fi
    printf '%-14s %-6s %8s  %s\n' regtool.py "$result" - "python <-> uart monitor"
fi

printf '\n%d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
