import { useEffect } from "react";

/**
 * Every modal in the app can be closed by clicking its Close button or the
 * backdrop — but not, until this, by pressing Escape, which is the standard
 * keyboard expectation for any dialog and the only way to dismiss one without
 * a mouse. Drop into any modal that takes an `onClose` prop.
 */
export function useEscapeToClose(onClose: () => void) {
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);
}
