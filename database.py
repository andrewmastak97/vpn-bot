import aiosqlite
import datetime
from typing import Optional, List, Tuple

DATABASE_NAME = "vpn_bot.db"

async def init_db():
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                start_date TIMESTAMP,
                end_date TIMESTAMP,
                subscription_type TEXT,
                payment_id TEXT,
                is_trial BOOLEAN DEFAULT FALSE,
                is_active BOOLEAN DEFAULT TRUE,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS wireguard_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                private_key TEXT,
                public_key TEXT,
                config_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)
        
        await db.commit()

async def add_user(user_id: int, username: str) -> bool:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        try:
            await db.execute(
                "INSERT INTO users (user_id, username) VALUES (?, ?)",
                (user_id, username)
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False

async def get_user(user_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            result = await cursor.fetchone()
            if result:
                return {
                    "user_id": result[0],
                    "username": result[1],
                    "registered_at": result[2],
                    "is_active": result[3]
                }
            return None

async def add_subscription(
    user_id: int,
    subscription_type: str,
    duration_months: int,
    payment_id: str,
    is_trial: bool = False
) -> bool:
    start_date = datetime.datetime.now()
    end_date = start_date + datetime.timedelta(days=30 * duration_months)
    
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            """
            INSERT INTO subscriptions 
            (user_id, start_date, end_date, subscription_type, payment_id, is_trial)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, start_date, end_date, subscription_type, payment_id, is_trial)
        )
        await db.commit()
        return True

async def get_active_subscription(user_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            """
            SELECT * FROM subscriptions 
            WHERE user_id = ? AND is_active = TRUE AND end_date > datetime('now')
            ORDER BY end_date DESC LIMIT 1
            """,
            (user_id,)
        ) as cursor:
            result = await cursor.fetchone()
            if result:
                return {
                    "id": result[0],
                    "user_id": result[1],
                    "start_date": result[2],
                    "end_date": result[3],
                    "subscription_type": result[4],
                    "payment_id": result[5],
                    "is_trial": result[6],
                    "is_active": result[7]
                }
            return None

async def save_wireguard_config(
    user_id: int,
    private_key: str,
    public_key: str,
    config_text: str
) -> bool:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            """
            INSERT INTO wireguard_configs 
            (user_id, private_key, public_key, config_text)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, private_key, public_key, config_text)
        )
        await db.commit()
        return True

async def get_expired_subscriptions() -> List[Tuple[int, str]]:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            """
            SELECT user_id, subscription_type FROM subscriptions
            WHERE is_active = TRUE AND end_date < datetime('now')
            """
        ) as cursor:
            return await cursor.fetchall()

async def deactivate_subscription(subscription_id: int) -> bool:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            "UPDATE subscriptions SET is_active = FALSE WHERE id = ?",
            (subscription_id,)
        )
        await db.commit()
        return True

async def extend_subscription(subscription_id: int, months: int) -> bool:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            """
            UPDATE subscriptions 
            SET end_date = datetime(end_date, '+' || ? || ' months')
            WHERE id = ?
            """,
            (months, subscription_id)
        )
        await db.commit()
        return True 