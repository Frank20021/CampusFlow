import type { TokenResponse, User } from "../types/api";
import { apiFetch } from "./client";

export type RegisterInput = {
  first_name: string;
  last_name: string;
  email: string;
  password: string;
  university?: string;
  major?: string;
};

export function register(input: RegisterInput) {
  return apiFetch<TokenResponse>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function login(email: string, password: string) {
  return apiFetch<TokenResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function getMe() {
  return apiFetch<User>("/api/users/me");
}

export function updateMe(input: Partial<Pick<User, "first_name" | "last_name" | "university" | "major">>) {
  return apiFetch<User>("/api/users/me", {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}
