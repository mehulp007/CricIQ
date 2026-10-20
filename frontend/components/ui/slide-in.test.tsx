import { render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { renderToString } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { RatingTrack } from "@/components/players/ratings";
import { SlideIn } from "@/components/ui/slide-in";
import type { Rating } from "@/lib/api/types";

function hydrate(ui: ReactElement) {
  const container = document.createElement("div");
  container.innerHTML = renderToString(ui);
  document.body.appendChild(container);
  return render(ui, { container, hydrate: true });
}

describe("SlideIn", () => {
  it("starts out of place when rendered in the browser", () => {
    render(
      <SlideIn from="left">
        <p>A new player</p>
      </SlideIn>,
    );
    const box = screen.getByText("A new player").parentElement!;
    expect(box).toHaveClass("slide-in");
    expect(box).toHaveAttribute("data-from", "left");
  });

  it("leaves what the visitor already sees in place", () => {
    hydrate(
      <SlideIn>
        <p>Already here</p>
      </SlideIn>,
    );
    const box = screen.getByText("Already here").parentElement!;
    expect(box).not.toHaveClass("slide-in");
  });
});

describe("RatingTrack", () => {
  it("places the band and the dot through CSS variables, so lists can grow them in", () => {
    const item = { label: "Strike rate", rating: 72, low: 60, high: 81, exposure_unit: "balls" };
    const { container } = render(<RatingTrack item={item as Rating} color="red" />);
    expect(container.querySelector(".rating-dot")).toHaveStyle({ "--at": "72%" });
    expect(container.querySelector(".rating-band")).toHaveStyle({ "--from": "60%", "--span": "21%" });
    expect(screen.getByRole("img")).toHaveAccessibleName(
      "Strike rate: 72 out of 100, 90% interval 60 to 81",
    );
  });
});
