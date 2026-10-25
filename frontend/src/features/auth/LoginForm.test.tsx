import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { LoginForm, emailError, passwordError } from "./LoginForm";

vi.mock("./AuthContext", () => ({
  useAuth: () => ({
    user: null,
    isLoading: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
  }),
}));

describe("login validation", () => {
  it("requires an email", () => {
    expect(emailError("")).toBe("Email is required");
  });

  it("rejects an invalid email", () => {
    expect(emailError("not-an-email")).toBe("Enter a valid email address");
  });

  it("requires a letter and a number in new passwords", () => {
    expect(passwordError("password")).toMatch(/letter and a number/);
    expect(passwordError("Secret123")).toBeUndefined();
  });
});

describe("LoginForm", () => {
  it("shows field errors when submitted empty", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <LoginForm />
      </MemoryRouter>,
    );
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("Email is required")).toBeInTheDocument();
    expect(screen.getByText("Password is required")).toBeInTheDocument();
  });
});
