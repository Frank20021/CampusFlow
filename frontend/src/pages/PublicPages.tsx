import { Link } from "react-router-dom";
import { LoginForm } from "../features/auth/LoginForm";
import { RegisterForm } from "../features/auth/RegisterForm";

export function LandingPage() {
  return (
    <div className="min-h-screen bg-stone-50">
      <header className="mx-auto flex max-w-5xl items-center justify-between px-4 py-5">
        <p className="text-sm font-semibold tracking-tight">CampusFlow</p>
        <nav className="flex items-center gap-4 text-sm">
          <Link to="/login" className="text-stone-700 hover:underline">
            Sign in
          </Link>
          <Link
            to="/register"
            className="rounded-md bg-teal-800 px-3 py-2 font-medium text-white hover:bg-teal-700"
          >
            Create account
          </Link>
        </nav>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-16">
        <p className="text-sm font-medium text-teal-800">For university students</p>
        <h1 className="mt-3 max-w-2xl text-4xl font-semibold tracking-tight text-stone-900 sm:text-5xl">
          Study groups that stay organized.
        </h1>
        <p className="mt-4 max-w-xl text-base leading-7 text-stone-600">
          Create a group for a course, invite classmates, and keep the work in one
          place — tasks, live chat, study sessions, shared links, and an inbox for
          what you missed.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link
            to="/register"
            className="rounded-md bg-teal-800 px-4 py-2.5 text-sm font-medium text-white hover:bg-teal-700"
          >
            Get started
          </Link>
          <Link
            to="/login"
            className="rounded-md border border-stone-300 bg-white px-4 py-2.5 text-sm font-medium text-stone-900 hover:bg-stone-50"
          >
            Sign in
          </Link>
        </div>
        <ul className="mt-16 grid gap-6 sm:grid-cols-3">
          {[
            ["Create groups", "Name a group, attach a course code, and you become the owner."],
            ["Join classmates", "Discover open groups and join in one click. Leave anytime."],
            ["Manage members", "Owners can update details, promote admins, and remove members."],
          ].map(([title, body]) => (
            <li key={title} className="border-t border-stone-200 pt-4">
              <h2 className="text-sm font-semibold text-stone-900">{title}</h2>
              <p className="mt-2 text-sm leading-6 text-stone-600">{body}</p>
            </li>
          ))}
        </ul>
      </main>
    </div>
  );
}

export function LoginPage() {
  return (
    <>
      <h1 className="text-xl font-semibold text-stone-900">Sign in</h1>
      <p className="mb-6 mt-1 text-sm text-stone-600">Use the email you registered with.</p>
      <LoginForm />
    </>
  );
}

export function RegisterPage() {
  return (
    <>
      <h1 className="text-xl font-semibold text-stone-900">Create your account</h1>
      <p className="mb-6 mt-1 text-sm text-stone-600">
        University and major can be added now or later on your profile.
      </p>
      <RegisterForm />
    </>
  );
}

export function NotFoundPage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-lg flex-col justify-center px-4">
      <p className="text-sm font-medium text-stone-500">404</p>
      <h1 className="mt-2 text-2xl font-semibold text-stone-900">Page not found</h1>
      <p className="mt-2 text-sm text-stone-600">
        That URL does not match a CampusFlow page.
      </p>
      <Link to="/" className="mt-6 text-sm font-medium text-teal-800 hover:underline">
        Back to home
      </Link>
    </main>
  );
}
