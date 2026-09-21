import React, { forwardRef } from "react";
import { RefreshCw } from "lucide-react";
import { cn } from "./utils";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "outline" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
  isLoading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = "primary",
      size = "md",
      isLoading = false,
      leftIcon,
      rightIcon,
      disabled,
      children,
      ...props
    },
    ref
  ) => {
    const baseStyles =
      "inline-flex items-center justify-center font-medium rounded-xl transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cool focus-visible:ring-offset-2 focus-visible:ring-offset-ink-bg disabled:opacity-50 disabled:cursor-not-allowed select-none active:scale-[0.98]";

    const variantStyles = {
      primary:
        "bg-gradient-to-r from-[#d4af37] to-[#b38e24] hover:from-[#e2bf48] hover:to-[#c49e2f] text-black font-semibold shadow-md hover:shadow-warm/20",
      secondary:
        "bg-ink-surface hover:bg-ink-elevated text-ink-text border border-ink-border hover:border-cool/50",
      outline:
        "bg-transparent hover:bg-ink-surface text-[#f1f3f7] border border-ink-border hover:border-[#d4af37]/60",
      ghost:
        "bg-transparent hover:bg-ink-surface/60 text-ink-muted hover:text-ink-text",
      danger:
        "bg-rose-950/40 hover:bg-rose-900/60 text-rose-200 border border-rose-800/60",
    };

    const sizeStyles = {
      sm: "text-xs px-3 py-1.5 min-h-[36px] gap-1.5",
      md: "text-sm px-4 py-2 min-h-[44px] gap-2",
      lg: "text-base px-6 py-2.5 min-h-[48px] gap-2.5",
    };

    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        className={cn(baseStyles, variantStyles[variant], sizeStyles[size], className)}
        {...props}
      >
        {isLoading ? (
          <RefreshCw className="w-4 h-4 animate-spin text-current" />
        ) : (
          leftIcon
        )}
        <span>{children}</span>
        {!isLoading && rightIcon}
      </button>
    );
  }
);

Button.displayName = "Button";
