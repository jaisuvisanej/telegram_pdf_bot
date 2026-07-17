import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import User, UserSetting
from src.database.repository import UserRepository
from src.models.schemas import UserCreate, UserSettingUpdate

logger = logging.getLogger(__name__)

class UserService:
    """Service handling User profiles and their preferences."""

    def __init__(self) -> None:
        self.user_repo = UserRepository()

    async def get_or_create_user(
        self, session: AsyncSession, telegram_id: int, username: Optional[str] = None, first_name: Optional[str] = None
    ) -> User:
        """Ensures a user exists in the system and retrieves their info."""
        user_data = UserCreate(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name
        )
        return await self.user_repo.get_or_create_user(session, user_data)

    async def get_user_settings(self, session: AsyncSession, telegram_id: int) -> Optional[UserSetting]:
        """Gets settings for a specific user."""
        user = await self.user_repo.get_user(session, telegram_id)
        if user:
            return user.settings
        return None

    async def update_user_settings(
        self, session: AsyncSession, telegram_id: int, settings_data: UserSettingUpdate
    ) -> Optional[UserSetting]:
        """Updates preferences such as target study language or currently selected PDF."""
        logger.info(f"Updating settings for user {telegram_id}: {settings_data.model_dump()}")
        return await self.user_repo.update_settings(session, telegram_id, settings_data)
