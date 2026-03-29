import ssl
from urllib.parse import urlsplit, urlunsplit, urlencode, parse_qsl

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from backend.core.config import settings


def _normalize(raw_url: str) -> tuple[str, dict]:
    """Make any Postgres URL work with the asyncpg driver.

    Accepts a plain `postgresql://` string (e.g. Neon's connection string) or an
    explicit `postgresql+asyncpg://` URL. Strips libpq-only query params that
    asyncpg rejects (sslmode, channel_binding) and enables TLS for remote hosts.
    """
    url = raw_url
    for prefix in ("postgresql+asyncpg://", "postgresql://", "postgres://"):
        if url.startswith(prefix):
            url = "postgresql+asyncpg://" + url[len(prefix):]
            break

    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    sslmode = query.pop("sslmode", None)
    query.pop("channel_binding", None)
    clean = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))

    connect_args: dict = {}
    host = parts.hostname or ""
    is_local = host in ("localhost", "127.0.0.1", "")
    # Managed Postgres (Neon, etc.) requires TLS; local docker does not.
    if ((not is_local and settings.app_env != "development") or
            sslmode in ("require", "verify-ca", "verify-full")):
        connect_args["ssl"] = ssl.create_default_context()

    return clean, connect_args


_db_url, _connect_args = _normalize(settings.postgres_url)

engine = create_async_engine(
    _db_url,
    echo=settings.app_env == "development",
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,   # Neon scales to zero — drop stale connections gracefully
    pool_recycle=300,
    connect_args=_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    """FastAPI dependency that provides a database session per request."""
    async with AsyncSessionLocal() as session:
        yield session
