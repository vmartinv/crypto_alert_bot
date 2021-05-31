source .venv/bin/activate
logfile="nohup.out"
if [ -f "$logfile" ]
then mv "$logfile" "$logfile.$(date +%F-%T)"
fi

python3 tg_bot_service.py
