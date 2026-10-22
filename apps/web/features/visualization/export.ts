import type { VisualizationView } from "@/lib/api";

export function exportSpecification(view: VisualizationView) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(view.result.data, null, 2) + "\n"], { type: "application/json" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `vision-specification-${view.id}-r${view.revision}.json`;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
