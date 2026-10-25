from app.repositories.group import GroupRepository
from app.repositories.membership import MembershipRepository
from app.repositories.message import MessageRepository
from app.repositories.notification import NotificationRepository
from app.repositories.resource import ResourceRepository
from app.repositories.study_session import SessionRepository
from app.repositories.task import TaskRepository
from app.repositories.user import UserRepository

user_repository = UserRepository()
group_repository = GroupRepository()
membership_repository = MembershipRepository()
task_repository = TaskRepository()
message_repository = MessageRepository()
session_repository = SessionRepository()
resource_repository = ResourceRepository()
notification_repository = NotificationRepository()
