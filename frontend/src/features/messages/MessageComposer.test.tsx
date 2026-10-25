import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { MessageComposer } from "./MessageComposer";

describe("MessageComposer", () => {
  it("sends the typed message", async () => {
    const onSend = vi.fn().mockResolvedValue(undefined);
    render(<MessageComposer onSend={onSend} />);

    await userEvent.type(screen.getByLabelText("Message"), "Meeting at six");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(onSend).toHaveBeenCalledWith("Meeting at six");
  });

  it("clears the box after a successful send", async () => {
    const onSend = vi.fn().mockResolvedValue(undefined);
    render(<MessageComposer onSend={onSend} />);

    const input = screen.getByLabelText("Message");
    await userEvent.type(input, "Sent{Enter}");

    await waitFor(() => expect(input).toHaveValue(""));
  });

  it("sends on Enter and adds a newline on Shift+Enter", async () => {
    const onSend = vi.fn().mockResolvedValue(undefined);
    render(<MessageComposer onSend={onSend} />);

    const input = screen.getByLabelText("Message");
    await userEvent.type(input, "line one{Shift>}{Enter}{/Shift}line two");
    expect(onSend).not.toHaveBeenCalled();
    expect(input).toHaveValue("line one\nline two");

    await userEvent.type(input, "{Enter}");
    expect(onSend).toHaveBeenCalledWith("line one\nline two");
  });

  it("refuses to send blank or whitespace-only messages", async () => {
    const onSend = vi.fn().mockResolvedValue(undefined);
    render(<MessageComposer onSend={onSend} />);

    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();

    await userEvent.type(screen.getByLabelText("Message"), "   {Enter}");
    expect(onSend).not.toHaveBeenCalled();
  });

  it("trims surrounding whitespace before sending", async () => {
    const onSend = vi.fn().mockResolvedValue(undefined);
    render(<MessageComposer onSend={onSend} />);

    await userEvent.type(screen.getByLabelText("Message"), "  padded  {Enter}");
    expect(onSend).toHaveBeenCalledWith("padded");
  });

  it("blocks and explains messages over the length limit", async () => {
    const onSend = vi.fn().mockResolvedValue(undefined);
    render(<MessageComposer onSend={onSend} />);

    const input = screen.getByLabelText("Message");
    await userEvent.click(input);
    await userEvent.paste("x".repeat(2001));

    expect(screen.getByRole("alert")).toHaveTextContent(/limited to 2000 characters/i);
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
    expect(input).toHaveAttribute("aria-invalid", "true");
  });

  it("keeps the text so it can be retried when sending fails", async () => {
    const onSend = vi.fn().mockRejectedValue(new Error("Network unreachable"));
    render(<MessageComposer onSend={onSend} />);

    const input = screen.getByLabelText("Message");
    await userEvent.type(input, "important{Enter}");

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("Network unreachable"),
    );
    expect(input).toHaveValue("important");
  });

  it("cannot be used when the caller has no access", () => {
    render(<MessageComposer onSend={vi.fn()} disabled />);

    expect(screen.getByLabelText("Message")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });
});
