import { z } from "zod";

export const QUESTION_MAX_LENGTH = 1000;
export const MAX_HISTORY_TURNS = 8; // the last 4 exchanges

export const chatTurnSchema = z.object({
  role: z.enum(["student", "tutor"]),
  content: z.string().trim().min(1).max(2000),
});

export const askRequestSchema = z.object({
  question: z.string({ error: "Escreva a sua dúvida." })
    .trim()
    .min(3, "Escreva a dúvida com pelo menos 3 caracteres.")
    .max(QUESTION_MAX_LENGTH, `Escreva a dúvida com no máximo ${QUESTION_MAX_LENGTH} caracteres.`),
  history: z.array(chatTurnSchema).max(MAX_HISTORY_TURNS).default([]),
  node_id: z.string().min(1).nullish(),
});

export const askResponseSchema = z.object({
  found_in_material: z.boolean(),
  answer: z.string().min(1),
  key_points: z.array(z.string()),
  example: z.string().nullish(),
  terms: z.array(z.object({ term: z.string(), definition: z.string() })),
  citations: z.array(z.object({
    chunk_index: z.number().int().nonnegative(),
    page_start: z.number().int().positive(),
    page_end: z.number().int().positive(),
    section_title: z.string().nullish(),
    excerpt: z.string(),
  })),
  related_concepts: z.array(z.object({ node_id: z.string(), label: z.string() })),
});
