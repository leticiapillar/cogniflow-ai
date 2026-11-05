import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { DOCUMENT_ID } from "@/features/mind-map/test-fixtures";
import { ApiError } from "@/services/http-client";
import { useTutor } from "../hooks/use-tutor";
import { askTutor } from "../services/ask-tutor";
import { createAnswer, createNotFoundAnswer } from "../test-fixtures";
import { TutorPanel } from "./tutor-panel";

vi.mock("../services/ask-tutor", () => ({ askTutor: vi.fn() }));

const ask = vi.mocked(askTutor);

beforeEach(() => { ask.mockReset(); });
afterEach(cleanup);

function Panel({ enabled = true }: { enabled?: boolean }) {
  const tutor = useTutor(DOCUMENT_ID);
  return <TutorPanel tutor={tutor} enabled={enabled} disabledMessage="O tira-dúvidas fica disponível quando o mapa estiver pronto." />;
}

async function askQuestion(text: string) {
  fireEvent.change(screen.getByLabelText("Sua dúvida"), { target: { value: text } });
  await act(async () => { fireEvent.submit(screen.getByRole("form", { name: "Pergunta para o tutor" })); });
}

it("is disabled until the map is ready", () => {
  render(<Panel enabled={false} />);

  expect((screen.getByLabelText("Sua dúvida") as HTMLTextAreaElement).closest("fieldset")?.disabled).toBe(true);
  expect(screen.getByText("O tira-dúvidas fica disponível quando o mapa estiver pronto.")).toBeTruthy();
});

it("shows the answer always in the same order, with pages, and focuses it", async () => {
  ask.mockResolvedValue(createAnswer());
  render(<Panel />);

  await askQuestion("O que a clorofila faz?");

  const conversation = screen.getByRole("list", { name: "Conversa com o tutor" });
  expect(within(conversation).getByText(/Você perguntou:/).parentElement?.textContent).toBe("Você perguntou: O que a clorofila faz?");

  const answer = screen.getByRole("article", { name: "Resposta do tutor" });
  expect(within(answer).getAllByRole("heading", { level: 5 }).map((heading) => heading.textContent))
    .toEqual(["Pontos principais", "Exemplo do material", "Termos", "Onde está no material"]);
  expect(within(answer).getByText("Página 2 · Seção: Cloroplastos")).toBeTruthy();
  expect(within(answer).getByText("Cloroplastos contêm clorofila.")).toBeTruthy();
  expect(document.activeElement).toBe(within(answer).getByRole("heading", { level: 4 }));
  expect((screen.getByLabelText("Sua dúvida") as HTMLTextAreaElement).value).toBe("");
});

it("suggests map concepts when the material has no answer", async () => {
  ask.mockResolvedValueOnce(createNotFoundAnswer()).mockResolvedValueOnce(createAnswer());
  render(<Panel />);

  await askQuestion("Quem ganhou a Copa de 1970?");

  expect(screen.getByText("Não encontrei isso no material da aula.")).toBeTruthy();
  expect(screen.queryByText("Onde está no material")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Perguntar sobre Clorofila" }));
  expect(screen.getByText(/Dúvida sobre o conceito:/).textContent).toContain("Clorofila");

  await askQuestion("O que ela faz?");
  expect(ask.mock.calls[1][1]).toMatchObject({ node_id: "chlorophyll" });
  expect(screen.getByText(/Você perguntou sobre Clorofila:/)).toBeTruthy();

  fireEvent.click(screen.getByRole("button", { name: "Remover conceito" }));
  expect(screen.queryByText(/Dúvida sobre o conceito:/)).toBeNull();
});

it("counts characters and limits the question length", () => {
  render(<Panel />);

  fireEvent.change(screen.getByLabelText("Sua dúvida"), { target: { value: "Clorofila?" } });

  expect(screen.getByText("10/1.000 caracteres")).toBeTruthy();
  expect((screen.getByLabelText("Sua dúvida") as HTMLTextAreaElement).maxLength).toBe(1000);
});

it("shows validation and API errors and focuses the API error", async () => {
  ask.mockImplementation(() => Promise.reject(
    new ApiError("http", "O tutor está indisponível no momento. Tente novamente em instantes.", 503),
  ));
  render(<Panel />);

  await askQuestion("oi");
  expect(screen.getByRole("alert").textContent).toBe("Escreva a dúvida com pelo menos 3 caracteres.");

  await askQuestion("O que é a clorofila?");
  const error = screen.getAllByRole("alert").find((element) => element.textContent?.includes("indisponível"));
  expect(document.activeElement).toBe(error);
});
