import type { z } from "zod";
import type { ApiError } from "@/services/http-client";
import type { askRequestSchema, askResponseSchema, chatTurnSchema } from "./schemas";

export type ChatTurn = z.infer<typeof chatTurnSchema>;
export type AskRequest = z.input<typeof askRequestSchema>;
export type AskResponse = z.infer<typeof askResponseSchema>;
export type Citation = AskResponse["citations"][number];

/** The map concept the question is about ("Tirar dúvida sobre este conceito"). */
export type ConceptContext = { nodeId: string; label: string };

export type TutorExchange = {
  id: number;
  question: string;
  concept?: ConceptContext;
} & (
  | { status: "pending" }
  | { status: "answered"; response: AskResponse }
  | { status: "error"; error: ApiError }
);
