import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CommandPalette } from "@/components/search/command-palette";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  usePathname: () => "/ipl/matches",
  useRouter: () => ({ push }),
}));

const SEARCH = {
  teams: [{ id: "MI", name: "Mumbai Indians", color: "#004ba0", active: true }],
  matches: [{ match_id: 1181768, headline: "IPL 2019 final", detail: "MI v CSK · 2019" }],
};
const PLAYERS = {
  items: [
    {
      player_id: "ba607b88",
      name: "Virat Kohli",
      role: "batter",
      team: "RCB",
      seasons: "2008–2026",
    },
  ],
};

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(url.includes("/players") ? PLAYERS : SEARCH),
      }),
    ),
  );
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  push.mockClear();
});

function renderPalette() {
  const onOpenChange = vi.fn();
  render(<CommandPalette open onOpenChange={onOpenChange} />);
  return { onOpenChange, input: screen.getByRole("combobox") };
}

describe("CommandPalette", () => {
  it("lists the competition's pages and featured replays before anything is typed", async () => {
    renderPalette();
    const list = screen.getByRole("listbox", { name: "Results" });
    expect(within(list).getByRole("option", { name: /Players/ })).toBeInTheDocument();
    expect(await within(list).findByRole("option", { name: /IPL 2019 final/ })).toBeInTheDocument();
    // Teams wait for a query.
    expect(within(list).queryByRole("option", { name: /Mumbai Indians/ })).toBeNull();
  });

  it("finds players as you type and opens the chosen one with Enter", async () => {
    const { input, onOpenChange } = renderPalette();
    fireEvent.change(input, { target: { value: "kohli" } });
    await act(async () => {
      vi.advanceTimersByTime(300);
    });
    const option = await screen.findByRole("option", { name: /Virat Kohli/ });
    // Move the highlight to it, then choose it.
    const options = screen.getAllByRole("option");
    for (let i = 0; i < options.indexOf(option); i++)
      fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(option).toHaveAttribute("aria-selected", "true");
    expect(input).toHaveAttribute("aria-activedescendant", option.id);
    fireEvent.keyDown(input, { key: "Enter" });
    expect(push).toHaveBeenCalledWith("/ipl/players/ba607b88");
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("matches teams by name once something is typed", async () => {
    const { input } = renderPalette();
    fireEvent.change(input, { target: { value: "mumbai" } });
    fireEvent.click(await screen.findByRole("option", { name: /Mumbai Indians/ }));
    expect(push).toHaveBeenCalledWith("/ipl/teams/MI");
  });

  it("says when nothing matches", () => {
    const { input } = renderPalette();
    fireEvent.change(input, { target: { value: "zzzz" } });
    expect(screen.getByText(/Nothing matches/)).toBeInTheDocument();
  });
});
