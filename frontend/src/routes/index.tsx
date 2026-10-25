import { createBrowserRouter } from "react-router-dom";
import { GuestRoute, ProtectedRoute } from "../features/auth/RouteGuards";
import { AppLayout, AuthLayout } from "../layouts/AppLayout";
import { DashboardPage } from "../pages/DashboardPage";
import { DiscoverGroupsPage } from "../pages/DiscoverGroupsPage";
import { GroupMembersPage } from "../pages/GroupMembersPage";
import { MessagesPage } from "../pages/MessagesPage";
import { MyGroupsPage } from "../pages/MyGroupsPage";
import { ProfilePage } from "../pages/ProfilePage";
import { LandingPage, LoginPage, NotFoundPage, RegisterPage } from "../pages/PublicPages";
import { ResourcesPage } from "../pages/ResourcesPage";
import { SessionsPage } from "../pages/SessionsPage";
import { StudyGroupPage } from "../pages/StudyGroupPage";
import { TasksPage } from "../pages/TasksPage";

export const router = createBrowserRouter([
  { path: "/", element: <LandingPage /> },
  {
    element: <GuestRoute />,
    children: [
      {
        element: <AuthLayout />,
        children: [
          { path: "/login", element: <LoginPage /> },
          { path: "/register", element: <RegisterPage /> },
        ],
      },
    ],
  },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { path: "/app", element: <DashboardPage /> },
          { path: "/app/groups", element: <MyGroupsPage /> },
          { path: "/app/groups/:groupId", element: <StudyGroupPage /> },
          { path: "/app/groups/:groupId/members", element: <GroupMembersPage /> },
          { path: "/app/groups/:groupId/tasks", element: <TasksPage /> },
          { path: "/app/groups/:groupId/messages", element: <MessagesPage /> },
          { path: "/app/groups/:groupId/sessions", element: <SessionsPage /> },
          { path: "/app/groups/:groupId/resources", element: <ResourcesPage /> },
          { path: "/app/discover", element: <DiscoverGroupsPage /> },
          { path: "/app/profile", element: <ProfilePage /> },
        ],
      },
    ],
  },
  { path: "*", element: <NotFoundPage /> },
]);
