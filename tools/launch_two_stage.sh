#!/bin/bash
# Launch the two-stage retrieval eval detached from the SSH session.
cd /root/autodl-tmp || exit 1
setsid nohup /root/autodl-tmp/condaenvs/metawingman/bin/python -X utf8 \
  /root/autodl-tmp/two-stage-retrieval-eval.py \
  > /root/autodl-tmp/two-stage-eval.log 2>&1 < /dev/null &
echo "LAUNCHED_PID=$!"
sleep 2
head -3 /root/autodl-tmp/two-stage-eval.log
