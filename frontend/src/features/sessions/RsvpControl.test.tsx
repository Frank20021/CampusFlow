import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { RsvpControl } from "./RsvpControl";

describe("RsvpControl", () => {
  it("exposes the choices as a labelled radio group", () => {
    render(<RsvpControl sessionTitle="Chapter 7" value={null} onChange={vi.fn()} />);

    const group = screen.getByRole("radiogroup", { name: /your response to chapter 7/i });
    expect(group).toBeInTheDocument();
    expect(screen.getAllByRole("radio")).toHaveLength(3);
  });

  it("marks the current answer as checked", () => {
    render(<RsvpControl sessionTitle="Chapter 7" value="maybe" onChange={vi.fn()} />);

    expect(screen.getByRole("radio", { name: "Maybe" })).toBeChecked();
    expect(screen.getByRole("radio", { name: "Going" })).not.toBeChecked();
  });

  it("reports the chosen answer", async () => {
    const onChange = vi.fn();
    render(<RsvpControl sessionTitle="Chapter 7" value={null} onChange={onChange} />);

    await userEvent.click(screen.getByRole("radio", { name: "Going" }));
    expect(onChange).toHaveBeenCalledWith("going");
  });

  it("withdraws the answer when the current one is picked again", async () => {
    const onChange = vi.fn();
    render(<RsvpControl sessionTitle="Chapter 7" value="going" onChange={onChange} />);

    await userEvent.click(screen.getByRole("radio", { name: "Going" }));
    expect(onChange).toHaveBeenCalledWith(null);
  });

  it("is inert while a response is saving", async () => {
    const onChange = vi.fn();
    render(<RsvpControl sessionTitle="Chapter 7" value={null} busy onChange={onChange} />);

    await userEvent.click(screen.getByRole("radio", { name: "Going" }));
    expect(onChange).not.toHaveBeenCalled();
  });
});
