import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ResourceForm } from "./ResourceForm";

async function fill(title: string, url: string) {
  await userEvent.type(screen.getByLabelText("Name"), title);
  await userEvent.type(screen.getByLabelText("Link"), url);
  await userEvent.click(screen.getByRole("button", { name: "Share link" }));
}

describe("ResourceForm", () => {
  it("shares a valid link", async () => {
    const onSubmit = vi.fn();
    render(<ResourceForm onSubmit={onSubmit} />);

    await fill("Lecture slides", "https://example.edu/slides.pdf");

    expect(onSubmit).toHaveBeenCalledWith({
      title: "Lecture slides",
      url: "https://example.edu/slides.pdf",
      description: null,
    });
  });

  it("requires a name", async () => {
    const onSubmit = vi.fn();
    render(<ResourceForm onSubmit={onSubmit} />);

    await userEvent.type(screen.getByLabelText("Link"), "https://example.edu");
    await userEvent.click(screen.getByRole("button", { name: "Share link" }));

    expect(screen.getByText("Give the link a name")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("asks for the full address when the scheme is missing", async () => {
    const onSubmit = vi.fn();
    render(<ResourceForm onSubmit={onSubmit} />);

    await fill("Notes", "example.edu/notes");

    expect(screen.getByText(/starting with https:\/\//i)).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("refuses a javascript: link", async () => {
    const onSubmit = vi.fn();
    render(<ResourceForm onSubmit={onSubmit} />);

    await fill("Totally safe", "javascript:alert(1)");

    expect(screen.getByText(/must start with http:\/\/ or https:\/\//i)).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("clears itself after a successful share", async () => {
    render(<ResourceForm onSubmit={vi.fn()} />);

    await fill("Lecture slides", "https://example.edu/slides.pdf");

    expect(screen.getByLabelText("Name")).toHaveValue("");
    expect(screen.getByLabelText("Link")).toHaveValue("");
  });

  it("passes an optional description through", async () => {
    const onSubmit = vi.fn();
    render(<ResourceForm onSubmit={onSubmit} />);

    await userEvent.type(screen.getByLabelText("Name"), "Notes");
    await userEvent.type(screen.getByLabelText("Link"), "https://example.edu");
    await userEvent.type(screen.getByLabelText("Why it is useful"), "Weeks 1-4");
    await userEvent.click(screen.getByRole("button", { name: "Share link" }));

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ description: "Weeks 1-4" }),
    );
  });

  it("surfaces a server-side rejection", () => {
    render(<ResourceForm serverError="That link was rejected" onSubmit={vi.fn()} />);
    expect(screen.getByRole("alert")).toHaveTextContent("That link was rejected");
  });
});
