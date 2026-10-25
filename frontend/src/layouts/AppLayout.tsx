import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../features/auth/AuthContext";
import { NotificationMenu } from "../features/notifications/NotificationMenu";
import { Button } from "../components/ui/Button";
import { fullName } from "../utils/format";
import { cn } from "../utils/format";

const nav = [
  { to: "/app", label: "Dashboard", end: true },
  { to: "/app/groups", label: "My groups" },
  { to: "/app/discover", label: "Discover" },
  { to: "/app/profile", label: "Profile" },
];

export function AppLayout() {
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen bg-stone-50 text-stone-900">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-white focus:px-3 focus:py-2"
      >
        Skip to content
      </a>
      <div className="mx-auto flex min-h-screen max-w-6xl">
        <aside className="hidden w-56 shrink-0 border-r border-stone-200 bg-white md:flex md:flex-col">
          <div className="border-b border-stone-200 px-5 py-5">
            <p className="text-sm font-semibold tracking-tight">CampusFlow</p>
            <p className="mt-1 text-xs text-stone-500">Study groups, organized.</p>
          </div>
          <nav aria-label="Application" className="flex flex-1 flex-col gap-1 p-3">
            {nav.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  cn(
                    "rounded-md px-3 py-2 text-sm",
                    isActive ? "bg-stone-100 font-medium text-stone-900" : "text-stone-600 hover:bg-stone-50",
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="border-t border-stone-200 p-4">
            <p className="truncate text-sm font-medium">{user ? fullName(user) : ""}</p>
            <p className="truncate text-xs text-stone-500">{user?.email}</p>
            <Button variant="ghost" size="sm" className="mt-2 w-full justify-start px-0" onClick={logout}>
              Sign out
            </Button>
          </div>
        </aside>
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex items-center justify-between border-b border-stone-200 bg-white px-4 py-3">
            <p className="text-sm font-semibold md:sr-only">CampusFlow</p>
            <div className="ml-auto flex items-center gap-1">
              <NotificationMenu enabled={Boolean(user)} />
              <Button variant="ghost" size="sm" className="md:hidden" onClick={logout}>
                Sign out
              </Button>
            </div>
          </header>
          <nav aria-label="Application" className="flex gap-1 overflow-x-auto border-b border-stone-200 bg-white px-2 py-2 md:hidden">
            {nav.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  cn(
                    "whitespace-nowrap rounded-md px-3 py-1.5 text-sm",
                    isActive ? "bg-stone-100 font-medium" : "text-stone-600",
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          <main id="main-content" className="flex-1 px-4 py-6 sm:px-8">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  );
}

export function AuthLayout() {
  return (
    <div className="min-h-screen bg-stone-50">
      <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-4 py-10">
        <p className="mb-6 text-sm font-semibold tracking-tight text-stone-900">CampusFlow</p>
        <div className="rounded-lg border border-stone-200 bg-white p-6">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
