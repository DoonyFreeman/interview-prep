import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Spinner } from "./Spinner";

type Variant = "primary" | "secondary" | "ghost";

const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-primary text-primary-fg hover:bg-primary-strong shadow-card disabled:opacity-50",
  secondary:
    "bg-surface text-ink border border-border hover:bg-surface-2 disabled:opacity-50",
  ghost: "text-primary hover:bg-primary-soft disabled:opacity-50",
};

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  /** Show a spinner and disable the button (e.g. while a mutation is pending). */
  loading?: boolean;
  children: ReactNode;
}

export function Button({
  variant = "primary",
  className = "",
  loading = false,
  disabled,
  children,
  ...rest
}: Props) {
  return (
    <button
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition-[background-color,box-shadow,transform] duration-150 active:scale-[0.97] disabled:cursor-not-allowed disabled:active:scale-100 ${VARIANTS[variant]} ${className}`}
      {...rest}
    >
      {loading && <Spinner />}
      {children}
    </button>
  );
}
