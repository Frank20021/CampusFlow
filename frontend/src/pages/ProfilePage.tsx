import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { updateMe } from "../api/auth";
import { ApiError } from "../api/client";
import { useAuth } from "../features/auth/AuthContext";
import { Alert } from "../components/ui/Feedback";
import { Button } from "../components/ui/Button";
import { TextField } from "../components/ui/Field";
import { PageHeader } from "../components/ui/Overlay";

export function ProfilePage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [firstName, setFirstName] = useState(user?.first_name ?? "");
  const [lastName, setLastName] = useState(user?.last_name ?? "");
  const [university, setUniversity] = useState(user?.university ?? "");
  const [major, setMajor] = useState(user?.major ?? "");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      updateMe({
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        university: university.trim() || null,
        major: major.trim() || null,
      }),
    onSuccess: (updated) => {
      queryClient.setQueryData(["me"], updated);
      setMessage("Profile saved.");
      setError(null);
    },
    onError: (err) => {
      setMessage(null);
      setError(err instanceof ApiError ? err.message : "Unable to save profile");
    },
  });

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    mutation.mutate();
  }

  return (
    <div className="max-w-xl">
      <PageHeader title="Profile" description="This information is visible to members of your groups." />
      {error ? <Alert>{error}</Alert> : null}
      {message ? (
        <p className="mb-4 text-sm text-teal-900" role="status">
          {message}
        </p>
      ) : null}
      <form onSubmit={onSubmit} className="flex flex-col gap-4 rounded-lg border border-stone-200 bg-white p-5">
        <TextField
          label="First name"
          value={firstName}
          onChange={(event) => setFirstName(event.target.value)}
          required
        />
        <TextField
          label="Last name"
          value={lastName}
          onChange={(event) => setLastName(event.target.value)}
          required
        />
        <TextField label="Email" value={user?.email ?? ""} disabled hint="Email cannot be changed in Phase 1." />
        <TextField
          label="University"
          value={university}
          onChange={(event) => setUniversity(event.target.value)}
        />
        <TextField label="Major" value={major} onChange={(event) => setMajor(event.target.value)} />
        <div>
          <Button type="submit" loading={mutation.isPending}>
            Save profile
          </Button>
        </div>
      </form>
    </div>
  );
}
