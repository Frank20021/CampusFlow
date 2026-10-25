export type MembershipRole = "owner" | "admin" | "member";

export type User = {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  university: string | null;
  major: string | null;
  created_at: string;
};

export type TokenResponse = {
  access_token: string;
  token_type: string;
  user: User;
};

export type StudyGroup = {
  id: string;
  name: string;
  description: string | null;
  course_code: string | null;
  owner_id: string;
  created_at: string;
  updated_at: string;
  member_count: number;
  my_role: MembershipRole | null;
};

export type GroupMember = {
  user_id: string;
  first_name: string;
  last_name: string;
  email: string;
  university: string | null;
  major: string | null;
  role: MembershipRole;
  joined_at: string;
};

export type TaskStatus = "TODO" | "IN_PROGRESS" | "DONE";
export type TaskPriority = "LOW" | "MEDIUM" | "HIGH";

export type TaskUser = {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
};

export type Task = {
  id: string;
  group_id: string;
  title: string;
  description: string | null;
  assigned_to: string | null;
  created_by: string;
  status: TaskStatus;
  priority: TaskPriority;
  due_date: string | null;
  created_at: string;
  updated_at: string;
  assignee: TaskUser | null;
  creator: TaskUser | null;
  can_delete: boolean;
};

export type MyTask = Task & { group_name: string };

export type RsvpStatus = "going" | "maybe" | "declined";

export type SessionUser = {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
};

export type RsvpCounts = {
  going: number;
  maybe: number;
  declined: number;
};

export type StudySession = {
  id: string;
  group_id: string;
  title: string;
  description: string | null;
  location: string | null;
  start_time: string;
  end_time: string;
  created_by: string;
  created_at: string;
  updated_at: string;
  creator: SessionUser | null;
  rsvp_counts: RsvpCounts;
  my_rsvp: RsvpStatus | null;
  can_manage: boolean;
};

export type MySession = StudySession & { group_name: string };

export type SessionAttendee = {
  user: SessionUser;
  status: RsvpStatus;
  responded_at: string;
};

export type Resource = {
  id: string;
  group_id: string;
  title: string;
  url: string;
  description: string | null;
  created_by: string;
  created_at: string;
  creator: SessionUser | null;
  can_delete: boolean;
};

export type MessageAuthor = {
  id: string;
  first_name: string;
  last_name: string;
};

export type Message = {
  id: string;
  group_id: string;
  user_id: string;
  content: string;
  created_at: string;
  author: MessageAuthor | null;
};

export type MessagePage = {
  items: Message[];
  has_more: boolean;
  next_cursor: string | null;
};

export type NotificationType =
  | "task_assigned"
  | "session_created"
  | "resource_shared"
  | "rsvp_updated";

export type NotificationActor = {
  id: string;
  first_name: string;
  last_name: string;
};

export type Notification = {
  id: string;
  user_id: string;
  actor_id: string | null;
  group_id: string | null;
  type: NotificationType;
  title: string;
  body: string;
  href: string;
  entity_id: string | null;
  read_at: string | null;
  created_at: string;
  actor: NotificationActor | null;
};

export type UnreadCount = {
  unread: number;
};

export type Paginated<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};

export type ApiErrorBody = {
  error: {
    code: string;
    message: string;
    details: Array<{ field?: string | null; message: string }>;
    request_id: string | null;
  };
};
