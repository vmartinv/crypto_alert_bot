A telegram bot with a powerful DSL to create alerts based on crypto prices and indicators. It uses Binance API.

**It supports following commands**

**/create <ALERT NAME> <ALERT CONDITION>**  
Get notified when the specified condition gets triggered. Alerts fire at most once per hour.

Example:
`/create btc_high price(btc/busd) > 45000` (notify me when BTC price goes higher than 45k USD)
`/create ema_test abs(ema(price(eth/busd), 7, 1h) - ema(price(eth/busd), 25, 1h)) < 0.1` (notify me when the difference between EMA 7 and EMA 25 on the 1h ETH/BUSD chart is less than 0.1)

Operators:
- Math: `+, -, *, /, abs`
- Comparison: `<, >, <=, >=`
- Logical: `and, or, if`
- Basic queries: `price, open, close, high, log, volume`
- Aggregate functions: `change, sma, smma, ema, rsi`

**/eval <EXPRESSION>**  
Gets the value of an expression,

Example:
`/eval abs(ema(price(eth/busd), 7, 1h) - ema(price(eth/busd), 25, 1h))`

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
