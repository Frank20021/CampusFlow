import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { listGroups } from "../api/groups";
import { listMySessions } from "../api/sessions";
import { listMyTasks } from "../api/tasks";
import { useAuth } from "../features/auth/AuthContext";
import { GroupCard } from "../features/groups/GroupCard";
import { EmptyState, Spinner } from "../components/ui/Feedback";
import { PageHeader } from "../components/ui/Overlay";
import {
  cn,
  formatDueDate,
  formatSessionRange,
  fullName,
  isOverdue,
  rsvpLabel,
  statusLabel,
} from "../utils/format";

export function DashboardPage() {
  const { user } = useAuth();
  const groupsQuery = useQuery({
    queryKey: ["groups", { mine: true }],
    queryFn: () => listGroups({ mine: true, limit: 6 }),
  });
  const myTasksQuery = useQuery({
    queryKey: ["tasks", "mine"],
    queryFn: () => listMyTasks(5),
  });
  const mySessionsQuery = useQuery({
    queryKey: ["my-sessions"],
    queryFn: () => listMySessions(5),
  });

  return (
    <div>
      <PageHeader
        title={`Welcome${user ? `, ${user.first_name}` : ""}`}
        description="Your groups, what is assigned to you, and what is coming up."
      />
      {user && (!user.university || !user.major) ? (
        <p className="mb-6 rounded-md border border-stone-200 bg-white px-4 py-3 text-sm text-stone-700">
          Finish your profile so classmates know who you are.{" "}
          <Link to="/app/profile" className="font-medium text-teal-800 hover:underline">
            Update profile
          </Link>
        </p>
      ) : null}

      <section aria-labelledby="my-groups-heading">
        <div className="mb-3 flex items-center justify-between">
          <h2 id="my-groups-heading" className="text-sm font-semibold text-stone-900">
            My study groups
          </h2>
          <Link to="/app/groups" className="text-sm font-medium text-teal-800 hover:underline">
            View all
          </Link>
        </div>
        {groupsQuery.isLoading ? <Spinner label="Loading groups" /> : null}
        {groupsQuery.data && groupsQuery.data.items.length === 0 ? (
          <EmptyState
            title="No groups yet"
            body="Create a group for a course, or discover groups your classmates already started."
            action={
              <div className="flex justify-center gap-3">
                <Link to="/app/groups" className="text-sm font-medium text-teal-800 hover:underline">
                  Create a group
                </Link>
                <Link to="/app/discover" className="text-sm font-medium text-teal-800 hover:underline">
                  Discover groups
                </Link>
              </div>
            }
          />
        ) : null}
        {groupsQuery.data && groupsQuery.data.items.length > 0 ? (
          <div className="grid gap-4 sm:grid-cols-2">
            {groupsQuery.data.items.map((group) => (
              <GroupCard key={group.id} group={group} />
            ))}
          </div>
        ) : null}
      </section>

      <section aria-labelledby="my-tasks-heading" className="mt-10">
        <h2 id="my-tasks-heading" className="mb-3 text-sm font-semibold text-stone-900">
          Tasks due soon
        </h2>
        {myTasksQuery.isLoading ? <Spinner label="Loading tasks" /> : null}
        {myTasksQuery.data && myTasksQuery.data.length === 0 ? (
          <p className="rounded-lg border border-dashed border-stone-300 bg-white px-4 py-6 text-center text-sm text-stone-600">
            Nothing is assigned to you right now.
          </p>
        ) : null}
        {myTasksQuery.data && myTasksQuery.data.length > 0 ? (
          <ul className="divide-y divide-stone-100 rounded-lg border border-stone-200 bg-white">
            {myTasksQuery.data.map((task) => (
              <li key={task.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
                <div className="min-w-0">
                  <Link
                    to={`/app/groups/${task.group_id}/tasks`}
                    className="text-sm font-medium text-stone-900 hover:underline"
                  >
                    {task.title}
                  </Link>
                  <p className="mt-0.5 text-xs text-stone-500">
                    {task.group_name} · {statusLabel(task.status)}
                  </p>
                </div>
                <span
                  className={cn(
                    "text-xs",
                    isOverdue(task.due_date, task.status)
                      ? "font-medium text-red-800"
                      : "text-stone-600",
                  )}
                >
                  {task.due_date ? formatDueDate(task.due_date) : "No due date"}
                </span>
              </li>
            ))}
          </ul>
        ) : null}
      </section>

      <section aria-labelledby="upcoming-sessions-heading" className="mt-10">
        <h2 id="upcoming-sessions-heading" className="mb-3 text-sm font-semibold text-stone-900">
          Upcoming sessions
        </h2>
        {mySessionsQuery.isLoading ? <Spinner label="Loading sessions" /> : null}
        {mySessionsQuery.data && mySessionsQuery.data.length === 0 ? (
          <p className="rounded-lg border border-dashed border-stone-300 bg-white px-4 py-6 text-center text-sm text-stone-600">
            Nothing scheduled in your groups yet.
          </p>
        ) : null}
        {mySessionsQuery.data && mySessionsQuery.data.length > 0 ? (
          <ul className="divide-y divide-stone-100 rounded-lg border border-stone-200 bg-white">
            {mySessionsQuery.data.map((session) => (
              <li
                key={session.id}
                className="flex flex-wrap items-center justify-between gap-2 px-4 py-3"
              >
                <div className="min-w-0">
                  <Link
                    to={`/app/groups/${session.group_id}/sessions`}
                    className="text-sm font-medium text-stone-900 hover:underline"
                  >
                    {session.title}
                  </Link>
                  <p className="mt-0.5 text-xs text-stone-500">
                    {session.group_name}
                    {session.location ? ` · ${session.location}` : ""}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-xs text-stone-600">
                    <time dateTime={session.start_time}>
                      {formatSessionRange(session.start_time, session.end_time)}
                    </time>
                  </p>
                  <p
                    className={cn(
                      "mt-0.5 text-xs",
                      session.my_rsvp === "going"
                        ? "font-medium text-teal-800"
                        : "text-stone-500",
                    )}
                  >
                    {rsvpLabel(session.my_rsvp)}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        ) : null}
      </section>

      <p className="sr-only">{user ? `Signed in as ${fullName(user)}` : ""}</p>
    </div>
  );
}
