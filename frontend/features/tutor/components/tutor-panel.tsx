import { useEffect, useId, useRef, useState, type Ref } from "react";
import { QUESTION_MAX_LENGTH } from "../schemas";
import type { useTutor } from "../hooks/use-tutor";
import { TutorAnswer } from "./tutor-answer";

type TutorPanelProps = {
  tutor: ReturnType<typeof useTutor>;
  enabled: boolean;
  disabledMessage: string;
  inputRef?: Ref<HTMLTextAreaElement>;
};

export function TutorPanel({ tutor, enabled, disabledMessage, inputRef }: TutorPanelProps) {
  const [question, setQuestion] = useState("");
  const idPrefix = useId();
  const answerHeadings = useRef(new Map<number, HTMLHeadingElement>());
  const errorMessage = useRef<HTMLParagraphElement>(null);
  const focusedExchange = useRef<number | null>(null);
  const { exchanges, concept, validationError, isAsking } = tutor;

  // Move focus to a new answer (or error) as soon as it arrives.
  useEffect(() => {
    const last = exchanges.at(-1);
    if (!last || last.status === "pending" || focusedExchange.current === last.id) return;
    focusedExchange.current = last.id;
    if (last.status === "answered") answerHeadings.current.get(last.id)?.focus();
    else errorMessage.current?.focus();
  }, [exchanges]);

  const submit = async () => {
    if (await tutor.ask(question)) setQuestion("");
  };

  return (
    <section aria-labelledby="tutor-heading" className="surface-card rounded-2xl p-6">
      <div className="flex items-center gap-3">
        <span aria-hidden="true" className="flex size-8 items-center justify-center rounded-lg bg-orange-50 text-sm font-bold text-[#c94627]">02</span>
        <h2 id="tutor-heading" className="text-lg font-semibold tracking-tight">Suas dúvidas</h2>
      </div>
      <p id="tutor-help" className="mt-2 text-sm leading-relaxed text-muted">
        Pergunte sobre a aula. O tutor responde só com o conteúdo do PDF e mostra a página de cada informação.
      </p>

      {exchanges.length > 0 && (
        <ol aria-label="Conversa com o tutor" className="mt-5 space-y-4">
          {exchanges.map((exchange) => (
            <li key={exchange.id} className="space-y-2">
              <p className="break-words rounded-xl bg-accent-soft px-4 py-3 text-sm">
                <span className="font-semibold">
                  Você perguntou{exchange.concept ? ` sobre ${exchange.concept.label}` : ""}:
                </span>{" "}
                {exchange.question}
              </p>
              {exchange.status === "pending" && (
                <p className="text-sm text-muted">O tutor está lendo o material…</p>
              )}
              {exchange.status === "answered" && (
                <TutorAnswer
                  response={exchange.response}
                  headingId={`${idPrefix}-answer-${exchange.id}`}
                  headingRef={(element) => {
                    if (element) answerHeadings.current.set(exchange.id, element);
                    else answerHeadings.current.delete(exchange.id);
                  }}
                  onSelectConcept={tutor.setConcept}
                />
              )}
              {exchange.status === "error" && (
                <p role="alert" tabIndex={-1}
                  ref={exchange.id === exchanges.at(-1)?.id ? errorMessage : undefined}
                  className="text-sm font-medium text-red-800">
                  {exchange.error.message}
                </p>
              )}
            </li>
          ))}
        </ol>
      )}

      <form
        aria-label="Pergunta para o tutor"
        noValidate
        className="mt-5"
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <fieldset disabled={!enabled} aria-describedby="tutor-help tutor-availability">
          <legend className="sr-only">Dúvida sobre o material</legend>

          {concept && (
            <div className="mb-3 flex flex-wrap items-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-sm">
              <span>Dúvida sobre o conceito: <span className="font-semibold">{concept.label}</span></span>
              <button type="button" onClick={() => tutor.setConcept(null)}
                className="rounded-md border border-border px-2 py-1 text-xs font-semibold">
                Remover conceito
              </button>
            </div>
          )}

          <label htmlFor="tutor-question" className="block text-sm font-semibold">Sua dúvida</label>
          <textarea
            ref={inputRef}
            id="tutor-question"
            rows={3}
            maxLength={QUESTION_MAX_LENGTH}
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            aria-invalid={Boolean(validationError)}
            aria-describedby={`tutor-count${validationError ? " tutor-error" : ""}`}
            placeholder="Ex.: O que a clorofila faz?"
            className="mt-2 block w-full resize-y rounded-xl border border-border bg-background px-3 py-3 text-sm transition-colors placeholder:text-muted focus:border-accent disabled:cursor-not-allowed disabled:bg-[#f1f2f6]"
          />
          <p id="tutor-count" className="mt-2 text-sm text-muted">{question.length}/1.000 caracteres</p>

          {validationError && (
            <p id="tutor-error" role="alert" className="mt-2 text-sm font-medium text-red-800">{validationError.message}</p>
          )}

          <div className="mt-4 flex flex-wrap gap-3">
            <button type="submit" disabled={isAsking}
              className="primary-button flex-1 rounded-lg bg-accent px-4 py-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-border disabled:text-muted disabled:shadow-none">
              {isAsking ? "O tutor está respondendo…" : "Perguntar"}
            </button>
            {isAsking && (
              <button type="button" onClick={tutor.cancel} className="rounded-lg border border-border px-4 py-3 text-sm font-semibold">
                Cancelar
              </button>
            )}
          </div>
        </fieldset>
      </form>

      <p id="tutor-availability" className="mt-3 text-sm text-muted">
        {enabled ? "Cada pergunta usa apenas o material enviado." : disabledMessage}
      </p>
    </section>
  );
}
