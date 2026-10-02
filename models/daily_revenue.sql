MODEL (
  name analytics.daily_revenue,
  kind INCREMENTAL_BY_TIME_RANGE (time_column order_date),
  cron '@daily',
  grain order_date,
  audits (not_null(columns := (order_date, paid_orders, revenue)), nonnegative_revenue)
);

SELECT
  order_date,
  COUNT(*)::INT AS paid_orders,
  SUM(amount)::DECIMAL(12, 2) AS revenue
FROM analytics.staged_orders
WHERE order_date BETWEEN @start_ds AND @end_ds AND status = 'paid'
GROUP BY order_date;
