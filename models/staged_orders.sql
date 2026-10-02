MODEL (
  name analytics.staged_orders,
  kind INCREMENTAL_BY_TIME_RANGE (time_column order_date),
  cron '@daily',
  grain order_id,
  audits (not_null(columns := (order_id, order_date, amount)), unique_values(columns := (order_id)), nonnegative_amount)
);

SELECT
  order_id::INT AS order_id,
  ordered_at::DATE AS order_date,
  amount::DECIMAL(12, 2) AS amount,
  LOWER(status)::TEXT AS status
FROM raw.orders
WHERE ordered_at::DATE BETWEEN @start_ds AND @end_ds;
