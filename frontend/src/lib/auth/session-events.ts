let generation = 0;
const listeners = new Set<() => void>();
export const sessionGeneration = () => generation;
export function onSessionCleared(listener: () => void): () => void {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}
export function sessionCleared(): void {
  generation++;
  for (const listener of listeners) listener();
}
