import { useEffect, useState, useCallback, createContext, useContext } from "react";

interface Toast {
  id: number;
  message: string;
  type: "info" | "error" | "success";
}

interface ToastContextValue {
  showToast: (message: string, type?: Toast["type"]) => void;
}

const ToastContext = createContext<ToastContextValue>({
  showToast: () => {},
});

export const useToast = () => useContext(ToastContext);

let _nextId = 0;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const showToast = useCallback((message: string, type: Toast["type"] = "info") => {
    const id = ++_nextId;
    setToasts((prev) => [...prev, { id, message, type }]);
  }, []);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div className="toast-stack" aria-live="polite">
        {toasts.map((t) => (
          <ToastItem key={t.id} toast={t} onDismiss={dismiss} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

function ToastItem({ toast, onDismiss }: { toast: Toast; onDismiss: (id: number) => void }) {
  const [exiting, setExiting] = useState(false);

  useEffect(() => {
    const autoHide = setTimeout(() => setExiting(true), 3500);
    return () => clearTimeout(autoHide);
  }, []);

  useEffect(() => {
    if (exiting) {
      const remove = setTimeout(() => onDismiss(toast.id), 400);
      return () => clearTimeout(remove);
    }
  }, [exiting, onDismiss, toast.id]);

  return (
    <div
      className={`toast toast-${toast.type} ${exiting ? "toast-exit" : "toast-enter"}`}
      onClick={() => setExiting(true)}
      role="status"
    >
      <span className="toast-icon">
        {toast.type === "error" ? "⚠" : toast.type === "success" ? "✓" : "ℹ"}
      </span>
      <span className="toast-message">{toast.message}</span>
    </div>
  );
}
