import { CircleCheck, CircleX, Info, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import type { Toast } from "../hooks/useDesk";

const ICONS = { ok: CircleCheck, bad: CircleX, info: Info };

export function Toasts({ toasts, onDismiss }: { toasts: Toast[]; onDismiss: (id: number) => void }) {
  return (
    <div className="toasts" role="status" aria-live="polite">
      <AnimatePresence initial={false}>
        {toasts.map((t) => {
          const Icon = ICONS[t.tone];
          return (
            <motion.div
              key={t.id}
              layout
              className={`toast toast--${t.tone}`}
              initial={{ opacity: 0, y: 16, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, x: 60, transition: { duration: 0.2 } }}
            >
              <Icon size={20} aria-hidden="true" />
              <div className="toast__body">
                <b>{t.title}</b>
                {t.text && <span>{t.text}</span>}
              </div>
              <button className="toast__close" onClick={() => onDismiss(t.id)} aria-label="Dismiss"><X size={15} /></button>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
