import os

from sqlmesh.core.config import (
    Config,
    DuckDBConnectionConfig,
    GatewayConfig,
    ModelDefaultsConfig,
    PostgresConnectionConfig,
)


def connection(prefix):
    return PostgresConnectionConfig(
        host=os.environ[f"{prefix}_HOST"],
        port=int(os.environ.get(f"{prefix}_PORT", "5432")),
        database=os.environ[f"{prefix}_DATABASE"],
        user=os.environ[f"{prefix}_USER"],
        password=os.environ[f"{prefix}_PASSWORD"],
        sslmode=os.environ.get(f"{prefix}_SSLMODE", "prefer"),
        connect_timeout=10,
        concurrent_tasks=1,
    )


config = Config(
    gateways={
        "postgres": GatewayConfig(
            connection=connection("WAREHOUSE"),
            state_connection=connection("STATE"),
            test_connection=DuckDBConnectionConfig(),
            state_schema="sqlmesh",
        )
    },
    default_gateway="postgres",
    model_defaults=ModelDefaultsConfig(dialect="postgres", start="2026-09-29"),
    disable_anonymized_analytics=True,
)
