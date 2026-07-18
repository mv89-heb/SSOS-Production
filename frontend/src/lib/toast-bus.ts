// Minimal pub/sub so non-component code (the axios interceptor) can trigger
// a toast without importing React. ToastProvider is the single subscriber;
// it registers itself on mount and clears itself on unmount.
export type ToastVariant = "error" | "info";

interface ToastMessage {
  id: number;
  message: string;
  variant: ToastVariant;
}

type Listener = (toast: ToastMessage) => void;

let listener: Listener | null = null;
let nextId = 1;

export function setToastListener(fn: Listener | null) {
  listener = fn;
}

export function emitToast(message: string, variant: ToastVariant = "error") {
  listener?.({ id: nextId++, message, variant });
}

export type { ToastMessage };
