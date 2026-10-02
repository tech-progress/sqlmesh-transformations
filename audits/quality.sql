AUDIT (name nonnegative_amount);
SELECT * FROM @this_model WHERE amount < 0;

AUDIT (name nonnegative_revenue);
SELECT * FROM @this_model WHERE revenue < 0 OR paid_orders < 1;
