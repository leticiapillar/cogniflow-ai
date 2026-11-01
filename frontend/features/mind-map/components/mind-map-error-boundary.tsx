import { Component, type ReactNode } from "react";

export class MindMapErrorBoundary extends Component<{ children: ReactNode; onShowList?: () => void }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (this.state.failed) {
      return <div className="space-y-3 rounded-xl border border-border p-4">
        <p role="alert" className="text-sm text-red-800">
          Não foi possível desenhar o mapa. Selecione Lista para consultar os conceitos.
        </p>
        {this.props.onShowList && <button type="button" onClick={this.props.onShowList}
          className="rounded-lg border border-border px-4 py-3 text-sm font-semibold">Ler em lista</button>}
      </div>;
    }

    return this.props.children;
  }
}
