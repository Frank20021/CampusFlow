from fastapi import APIRouter

from app.api.routes import auth, groups, messages, notifications, resources, sessions, tasks, users

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(groups.router, prefix="/groups", tags=["groups"])
api_router.include_router(tasks.group_tasks_router, prefix="/groups", tags=["tasks"])
api_router.include_router(tasks.tasks_router, prefix="/tasks", tags=["tasks"])
api_router.include_router(messages.group_messages_router, prefix="/groups", tags=["messages"])
api_router.include_router(messages.messages_router, prefix="/messages", tags=["messages"])
api_router.include_router(sessions.group_sessions_router, prefix="/groups", tags=["sessions"])
api_router.include_router(sessions.sessions_router, prefix="/sessions", tags=["sessions"])
api_router.include_router(resources.group_resources_router, prefix="/groups", tags=["resources"])
api_router.include_router(resources.resources_router, prefix="/resources", tags=["resources"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
