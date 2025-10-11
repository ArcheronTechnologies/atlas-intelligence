"""
Database connection and management for Atlas Intelligence
"""

import asyncpg
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text

from config.settings import settings
from database.models import Base

logger = logging.getLogger(__name__)


class AtlasDatabase:
    """Database manager for Atlas Intelligence"""

    def __init__(self):
        self.engine = None
        self.session_factory = None
        self.pool = None

    async def initialize(self):
        """Initialize database connections"""
        try:
            # Create SQLAlchemy async engine
            database_url = settings.DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://')

            self.engine = create_async_engine(
                database_url,
                pool_size=10,
                max_overflow=20,
                echo=settings.DEBUG,
                future=True
            )

            # Create session factory
            self.session_factory = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )

            # Create direct asyncpg pool for raw queries
            async def init_conn(conn):
                await conn.execute("SET search_path TO public")

            self.pool = await asyncpg.create_pool(
                settings.DATABASE_URL,
                min_size=5,
                max_size=20,
                timeout=30,
                command_timeout=60,
                max_inactive_connection_lifetime=300,
                init=init_conn
            )

            # Ensure PostGIS extension
            await self._ensure_postgis()

            # Create tables
            await self._create_tables()

            logger.info("✅ Atlas database initialized")

        except Exception as e:
            logger.error("❌ Database initialization failed: %s", e)
            logger.warning("⚠️ Continuing without full initialization - use admin API to reset database")

    async def _ensure_postgis(self):
        """Ensure PostGIS extension is enabled"""
        async with self.pool.acquire() as conn:
            try:
                await conn.execute("CREATE EXTENSION IF NOT EXISTS postgis")
                await conn.execute("CREATE EXTENSION IF NOT EXISTS postgis_topology")
                logger.info("✅ PostGIS extensions enabled")
            except Exception as e:
                logger.warning("⚠️ Could not enable PostGIS: %s", e)

    async def _create_tables(self):
        """Create database tables"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Database tables created/verified")

    async def get_session(self):
        """Get async database session"""
        async with self.session_factory() as session:
            try:
                await session.execute(text("SET search_path TO public"))
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def execute_query(self, query: str, *params):
        """Execute raw SQL query"""
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *params)

    async def execute_single(self, query: str, *params):
        """Execute query and return single result"""
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *params)

    async def close(self):
        """Close database connections"""
        if self.pool:
            await self.pool.close()
        if self.engine:
            await self.engine.dispose()
        logger.info("🔒 Database connections closed")


# Singleton instance
_database: Optional[AtlasDatabase] = None


async def get_database() -> AtlasDatabase:
    """Get database instance"""
    global _database
    if _database is None:
        _database = AtlasDatabase()
    return _database
