import type { Ref } from "react";
import type { AskResponse, Citation, ConceptContext } from "../types";

function pagesLabel(citation: Pick<Citation, "page_start" | "page_end">): string {
  return citation.page_start === citation.page_end
    ? `Página ${citation.page_start}`
    : `Páginas ${citation.page_start} a ${citation.page_end}`;
}

type TutorAnswerProps = {
  response: AskResponse;
  headingRef?: Ref<HTMLHeadingElement>;
  headingId: string;
  onSelectConcept?: (concept: ConceptContext) => void;
};

/** Always the same order: answer -> key points -> example -> terms -> where it is in the PDF. */
export function TutorAnswer({ response, headingRef, headingId, onSelectConcept }: TutorAnswerProps) {
  return (
    <article aria-labelledby={headingId} className="space-y-3 rounded-xl border border-border bg-surface p-4 text-sm leading-relaxed">
      <h4 id={headingId} ref={headingRef} tabIndex={-1} className="text-xs font-bold uppercase tracking-[0.1em] text-muted">
        Resposta do tutor
      </h4>
      <p className="text-base font-semibold">{response.answer}</p>

      {!response.found_in_material && response.related_concepts.length > 0 && (
        <div>
          <h5 className="font-semibold">Conceitos do mapa para explorar</h5>
          <ul className="mt-2 flex flex-wrap gap-2">
            {response.related_concepts.map((concept) => (
              <li key={concept.node_id}>
                <button type="button"
                  onClick={() => onSelectConcept?.({ nodeId: concept.node_id, label: concept.label })}
                  className="rounded-lg border border-border px-3 py-1.5 font-semibold text-accent">
                  Perguntar sobre {concept.label}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {response.key_points.length > 0 && (
        <div>
          <h5 className="font-semibold">Pontos principais</h5>
          <ul className="mt-1 list-disc space-y-1 pl-5">
            {response.key_points.map((point) => <li key={point}>{point}</li>)}
          </ul>
        </div>
      )}

      {response.example && (
        <div>
          <h5 className="font-semibold">Exemplo do material</h5>
          <p className="mt-1">{response.example}</p>
        </div>
      )}

      {response.terms.length > 0 && (
        <div>
          <h5 className="font-semibold">Termos</h5>
          <dl className="mt-1 space-y-1">
            {response.terms.map((term) => (
              <div key={term.term}><dt className="inline font-semibold">{term.term}:</dt> <dd className="inline">{term.definition}</dd></div>
            ))}
          </dl>
        </div>
      )}

      {response.citations.length > 0 && (
        <div>
          <h5 className="font-semibold">Onde está no material</h5>
          <ul className="mt-1 space-y-2">
            {response.citations.map((citation) => (
              <li key={citation.chunk_index} className="rounded-lg bg-background p-3">
                <p className="font-semibold">
                  {pagesLabel(citation)}
                  {citation.section_title ? ` · Seção: ${citation.section_title}` : ""}
                </p>
                <blockquote className="mt-1 border-l-2 border-border pl-3 text-muted">{citation.excerpt}</blockquote>
              </li>
            ))}
          </ul>
        </div>
      )}
    </article>
  );
}
