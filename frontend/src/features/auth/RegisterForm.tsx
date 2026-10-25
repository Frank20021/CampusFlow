import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError } from "../../api/client";
import { Alert } from "../../components/ui/Feedback";
import { Button } from "../../components/ui/Button";
import { TextField } from "../../components/ui/Field";
import { useAuth } from "./AuthContext";
import { emailError, passwordError } from "./LoginForm";

function requiredName(value: string, label: string): string | undefined {
  if (!value.trim()) return `${label} is required`;
  return undefined;
}

export function RegisterForm() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [university, setUniversity] = useState("");
  const [major, setMajor] = useState("");
  const [errors, setErrors] = useState<Record<string, string | undefined>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const next = {
      firstName: requiredName(firstName, "First name"),
      lastName: requiredName(lastName, "Last name"),
      email: emailError(email),
      password: passwordError(password),
    };
    setErrors(next);
    if (Object.values(next).some(Boolean)) return;

    setBusy(true);
    setSubmitError(null);
    try {
      await register({
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        email,
        password,
        university: university.trim() || undefined,
        major: major.trim() || undefined,
      });
      void navigate("/app");
    } catch (error) {
      setSubmitError(error instanceof ApiError ? error.message : "Unable to create account");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
      {submitError ? <Alert>{submitError}</Alert> : null}
      <div className="grid gap-4 sm:grid-cols-2">
        <TextField
          label="First name"
          autoComplete="given-name"
          value={firstName}
          onChange={(event) => setFirstName(event.target.value)}
          error={errors.firstName}
          required
        />
        <TextField
          label="Last name"
          autoComplete="family-name"
          value={lastName}
          onChange={(event) => setLastName(event.target.value)}
          error={errors.lastName}
          required
        />
      </div>
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
        autoComplete="new-password"
        value={password}
        onChange={(event) => setPassword(event.target.value)}
        error={errors.password}
        hint="At least 8 characters, including a letter and a number."
        required
      />
      <TextField
        label="University"
        autoComplete="organization"
        value={university}
        onChange={(event) => setUniversity(event.target.value)}
      />
      <TextField
        label="Major"
        value={major}
        onChange={(event) => setMajor(event.target.value)}
      />
      <Button type="submit" loading={busy}>
        Create account
      </Button>
      <p className="text-sm text-stone-600">
        Already have an account?{" "}
        <Link to="/login" className="font-medium text-teal-800 underline-offset-2 hover:underline">
          Sign in
        </Link>
      </p>
    </form>
  );
}
