import type { z } from "zod";
import type { documentUploadResponseSchema } from "./schemas";
import type { ApiError } from "@/services/http-client";

export type DocumentUploadResponse = z.infer<typeof documentUploadResponseSchema>;

export type IngestionState =
  | { status: "idle" }
  | { status: "uploading" }
  | { status: "success"; document: DocumentUploadResponse }
  | { status: "error"; error: ApiError };
