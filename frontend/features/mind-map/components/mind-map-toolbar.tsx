type ToolbarProps = {
  onZoomIn: () => void;
  onZoomOut: () => void;
  onFitView: () => void;
  onReorganize: () => void;
};

export function MindMapToolbar({ onZoomIn, onZoomOut, onFitView, onReorganize }: ToolbarProps) {
  const actions = [
    { icon: "+", label: "Aumentar zoom", name: "Aumentar zoom", run: onZoomIn },
    { icon: "−", label: "Diminuir zoom", name: "Diminuir zoom", run: onZoomOut },
    { icon: "⌗", label: "Ajustar à tela", name: "Ajustar à tela", run: onFitView },
    { icon: "↻", label: "Reorganizar", name: "Reorganizar mapa", run: onReorganize },
  ];

  return (
    <div role="group" aria-label="Controles do mapa" className="flex flex-wrap gap-2 rounded-xl border border-border bg-background/80 p-2">
      {actions.map((action) => (
        <button key={action.name} type="button" aria-label={action.name} onClick={action.run}
          className="inline-flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2 text-sm font-semibold shadow-sm transition-colors hover:border-[#bbb7e8] hover:bg-accent-soft">
          <span aria-hidden="true" className="text-base text-accent">{action.icon}</span>{action.label}
        </button>
      ))}
    </div>
  );
}
