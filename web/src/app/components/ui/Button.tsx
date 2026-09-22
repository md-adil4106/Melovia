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
        "bg-gradient-to-r from-[#fa2d55] via-[#e11d48] to-[#be123c] hover:from-[#ff375f] hover:to-[#d01344] text-white font-semibold shadow-ruby hover:shadow-ruby-lg",
      secondary:
        "bg-white/[0.06] hover:bg-white/[0.12] text-white border border-white/10 hover:border-white/20 backdrop-blur-md",
      outline:
        "bg-transparent hover:bg-white/[0.06] text-white border border-white/15 hover:border-[#fa2d55]/60",
      ghost:
        "bg-transparent hover:bg-white/[0.06] text-white/70 hover:text-white",
      danger:
        "bg-rose-950/50 hover:bg-rose-900/70 text-rose-200 border border-rose-500/30",
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
