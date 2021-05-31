**This bot supports following commands**

**/create <ALERT NAME> <ALERT CONDITION>**  
Get notified when the specified condition gets triggered.

Example:
`/create btc_high price(btc/busd) > 45000` (notify me when BTC price goes higher than 45k USD)  
`/create chg_high change(price(eth/busd), 24h)>10%` (notify me when ETH price changes more than 10% in the last 24 hours)
`/create ema_test abs(ema(eth/busd, 7, 1h) - ema(eth/busd, 25, 1h)) < 0.1` (notify me when the difference between EMA 7 and EMA 25 on the 1h ETH/BUSD chart is less than 0.1)

**/eval <EXPRESSION>**  
Gets the value of an expression,

Example:
`/eval abs(ema(eth/busd, 7, 1h) - ema(eth/busd, 25, 1h))`

**/list**  
Get the active alerts.

**/remove <ALERT NAME>**  
Remove an alert.

**/remove**  
Clear all alerts.

**/help**  
See this message.

**Source**
https://github.com/vmartinv/price_alert_bot/
