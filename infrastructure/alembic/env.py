from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from tourism_pulse_api.db.base import Base
from tourism_pulse_api.settings import settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


POSTGIS_TABLES = {
    "spatial_ref_sys",
    "geography_columns",
    "geometry_columns",
    "raster_columns",
    "raster_overviews",
    "layer",
    "topology",
    "loader_platform",
    "loader_lookuptables",
    "loader_variables",
    "pagc_gaz",
    "pagc_lex",
    "pagc_rules",
    "place",
    "place_lookup",
    "county",
    "county_lookup",
    "state",
    "state_lookup",
    "cousub",
    "countysub_lookup",
    "tract",
    "bg",
    "faces",
    "edges",
    "addr",
    "addrfeat",
    "featnames",
    "tabblock",
    "tabblock20",
    "zcta5",
    "zip_lookup",
    "zip_lookup_all",
    "zip_lookup_base",
    "zip_state",
    "zip_state_loc",
    "geocode_settings",
    "geocode_settings_default",
    "secondary_unit_lookup",
    "direction_lookup",
    "street_type_lookup",
}


def include_object(object_, name, type_, reflected, compare_to):
    if type_ == "table" and reflected and name in POSTGIS_TABLES:
        return False

    return True

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")

    context.configure(
    url=url,
    target_metadata=target_metadata,
    include_object=include_object,
    literal_binds=True,
    dialect_opts={"paramstyle": "named"},
)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
    connection=connection,
    target_metadata=target_metadata,
    include_object=include_object,
)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
