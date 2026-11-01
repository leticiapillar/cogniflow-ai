import { z } from "zod";

export const MAX_PDF_SIZE_BYTES = 20 * 1024 * 1024;

export const pdfFileSchema = z.instanceof(File, { error: "Selecione um arquivo PDF válido." })
  .refine((file) => file.name.trim().toLowerCase().endsWith(".pdf"), "Selecione um arquivo com extensão .pdf.")
  .refine((file) => file.size > 0, "O arquivo está vazio. Selecione outro PDF.")
  .refine((file) => file.size <= MAX_PDF_SIZE_BYTES, "O PDF deve ter no máximo 20 MiB.")
  .refine(
    (file) => ["", "application/pdf", "application/octet-stream"].includes(file.type),
    "O tipo do arquivo não é aceito. Selecione um PDF.",
  );

export const documentUploadResponseSchema = z.object({
  document_name: z.string().trim().min(1),
  total_chunks: z.number().int().nonnegative(),
  message: z.string(),
});
