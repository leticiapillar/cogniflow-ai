import type { ReactNode } from "react";

export function StatusMessage({ children }: { children: ReactNode }) {
  return (
    <div
      role="status"
      aria-atomic="true"
      className="flex break-words rounded-xl border border-border bg-surface/80 px-5 py-4 text-sm leading-relaxed text-muted shadow-sm"
    >
      <span aria-hidden="true" className="mr-3 mt-1 size-2 shrink-0 rounded-full bg-accent shadow-[0_0_0_4px_var(--accent-soft)]" />
      <span>{children}</span>
    </div>
  );
}
