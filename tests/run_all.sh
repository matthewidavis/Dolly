#!/usr/bin/env bash
# Run every Dolly test suite, one at a time, and print a one-line verdict per suite.
# Usage:  ./run_all.sh            (all suites)
#         ./run_all.sh uitest     (one or more named suites)
# Each suite prints "ERRORS: none" when clean. The full run takes several minutes.
cd "$(dirname "$0")"
SUITES="uitest reordertest playheadtest gesturetest rotatetest cornertest autoplaytest undotest projtest projectstest
recoverytest queuetest pintest giftest videotest fittest naturaltest soundtest motiontest mp4test lighttest
motionpathtest styletest lifetest flowtest leaktest arctest curvetest frametest looktest paneltest docktest desktest"
[ $# -gt 0 ] && SUITES="$*"
mkdir -p out/logs
pass=0; fail=0; failed=""
for t in $SUITES; do
  if timeout 400 python3 "$t.py" > "out/logs/$t.log" 2>&1 && grep -q "ERRORS: none" "out/logs/$t.log"; then
    pass=$((pass+1)); echo "  ok    $t"
  else
    fail=$((fail+1)); failed="$failed $t"; echo "  FAIL  $t   (see out/logs/$t.log)"
  fi
done
echo "clean: $pass of $((pass+fail))${failed:+ | failed:$failed}"
[ $fail -eq 0 ]
