import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError } from "../../api/client";
import { Alert } from "../../components/ui/Feedback";
import { Button } from "../../components/ui/Button";
import { TextField } from "../../components/ui/Field";
import { useAuth } from "./AuthContext";

export function emailError(value: string): string | undefined {
  if (!value.trim()) return "Email is required";
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) return "Enter a valid email address";
  return undefined;
}

export function passwordError(value: string): string | undefined {
  if (!value) return "Password is required";
  if (value.length < 8) return "Password must be at least 8 characters";
  if (!/[A-Za-z]/.test(value) || !/\d/.test(value)) {
    return "Password must include a letter and a number";
  }
  return undefined;
}

export function LoginForm() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const next = {
      email: emailError(email),
      password: password ? undefined : "Password is required",
    };
    setErrors(next);
    if (next.email || next.password) return;

    setBusy(true);
    setSubmitError(null);
    try {
      await login(email, password);
      void navigate("/app");
    } catch (error) {
      setSubmitError(error instanceof ApiError ? error.message : "Unable to sign in");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
      {submitError ? <Alert>{submitError}</Alert> : null}
      <TextField
        label="Email"
        type="email"
        autoComplete="email"
        value={email}
        onChange={(event) => setEmail(event.target.value)}
        error={errors.email}
        required
      />
      <TextField
        label="Password"
        type="password"
        autoComplete="current-password"
        value={password}
        onChange={(event) => setPassword(event.target.value)}
        error={errors.password}
        required
      />
      <Button type="submit" loading={busy}>
        Sign in
      </Button>
      <p className="text-sm text-stone-600">
        New to CampusFlow?{" "}
        <Link to="/register" className="font-medium text-teal-800 underline-offset-2 hover:underline">
          Create an account
        </Link>
      </p>
    </form>
  );
}
