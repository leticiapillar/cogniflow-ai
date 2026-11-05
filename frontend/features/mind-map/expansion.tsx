import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import type { MindMap } from "./types";
import { childrenByParent, topicsInOrder } from "./utils/tree";

export type TopicExpansion = {
  expanded: ReadonlySet<string>;
  isExpanded: (topicId: string) => boolean;
  toggle: (topicId: string) => void;
  open: (topicId: string) => void;
  expandAll: () => void;
  collapseAll: () => void;
  conceptCount: (topicId: string) => number;
};

/** Which study axes are open. Starts closed: the student sees the theme and the axes first. */
export function useTopicExpansion(map: MindMap): TopicExpansion {
  const [expanded, setExpanded] = useState<ReadonlySet<string>>(() => new Set());
  const children = useMemo(() => childrenByParent(map), [map]);
  const topicIds = useMemo(() => topicsInOrder(map).map((topic) => topic.id), [map]);

  const toggle = useCallback((topicId: string) => {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(topicId)) next.delete(topicId);
      else next.add(topicId);
      return next;
    });
  }, []);

  const open = useCallback((topicId: string) => {
    setExpanded((current) => (current.has(topicId) ? current : new Set([...current, topicId])));
  }, []);

  const expandAll = useCallback(() => setExpanded(new Set(topicIds)), [topicIds]);
  const collapseAll = useCallback(() => setExpanded(new Set()), []);

  return useMemo(() => ({
    expanded,
    isExpanded: (topicId: string) => expanded.has(topicId),
    toggle,
    open,
    expandAll,
    collapseAll,
    conceptCount: (topicId: string) => (children.get(topicId) ?? []).length,
  }), [children, collapseAll, expandAll, expanded, open, toggle]);
}

const ExpansionContext = createContext<TopicExpansion | null>(null);

export function TopicExpansionProvider({ value, children }: { value: TopicExpansion; children: ReactNode }) {
  return <ExpansionContext.Provider value={value}>{children}</ExpansionContext.Provider>;
}

export function useExpansionContext(): TopicExpansion | null {
  return useContext(ExpansionContext);
}

export function conceptCountLabel(count: number): string {
  return `${count} ${count === 1 ? "conceito" : "conceitos"}`;
}
