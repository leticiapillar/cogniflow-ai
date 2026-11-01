import { execFile } from "node:child_process";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { promisify } from "node:util";

export function assertLocalApi(url: string) {
  const parsed = new URL(url);
  if (!["http:", "https:"].includes(parsed.protocol) ||
      !["127.0.0.1", "localhost", "[::1]"].includes(parsed.hostname)) {
    throw new Error("Os testes reais devem usar o FastAPI local.");
  }
}

export function readProposalPdf() {
  return readFile(resolve(process.cwd(), "../Proposta_Projeto_CogniFlow_AI.pdf"));
}

export async function removeTestDocument(name: string) {
  if (!/^cogniflow-stage[235]-[0-9a-f-]+\.pdf$/.test(name)) {
    throw new Error("Nome de documento fora do escopo de limpeza dos testes.");
  }
  const backend = resolve(process.cwd(), "../backend");
  await promisify(execFile)(resolve(backend, ".venv/bin/python"), ["-c", `
import asyncio
import sys
from sqlalchemy import delete
from app.core.database import engine
from app.repositories.models import DocumentChunkModel
async def cleanup():
    async with engine.begin() as connection:
        await connection.execute(delete(DocumentChunkModel).where(DocumentChunkModel.document_name == sys.argv[1]))
    await engine.dispose()
asyncio.run(cleanup())
`, name], { cwd: backend });
}
