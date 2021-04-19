#!/usr/bin/env bash
PIDFILE=daemon.pid

if [ -f $PIDFILE ]
then
  PID=$(cat $PIDFILE)
  kill $PID
fi

logfile="nohup.out"
if [ -f "$logfile" ]
then mv "$logfile" "$logfile.$(date +%F-%T)"
fi

source .venv/bin/activate
pip install -r requirements.txt
python3 tg_bot_service.py >$logfile 2>&1 &
echo $! > $PIDFILE
if [ $? -ne 0 ]
then
  echo "Could not create PID file"
  exit 1
fi
