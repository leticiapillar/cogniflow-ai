import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { MindMapErrorBoundary } from "./mind-map-error-boundary";

afterEach(cleanup);

it("keeps a recoverable message when the canvas throws during rendering", () => {
  vi.spyOn(console, "error").mockImplementation(() => {});
  function BrokenCanvas(): never { throw new Error("Rendering failure"); }
  const recover = vi.fn();

  render(<MindMapErrorBoundary onShowList={recover}><BrokenCanvas /></MindMapErrorBoundary>);

  expect(screen.getByRole("alert").textContent).toContain("Selecione Lista");
  fireEvent.click(screen.getByRole("button", { name: "Ler em lista" }));

  expect(recover).toHaveBeenCalledTimes(1);
});
