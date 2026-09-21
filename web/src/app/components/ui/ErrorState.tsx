import React from "react";
import { AlertCircle, RefreshCw } from "lucide-react";
import { Button } from "./Button";
import { cn } from "./utils";

export interface ErrorStateProps {
  title?: string;
  message: string;
  requestId?: string | null;
  onRetry?: () => void;
  className?: string;
}

export function ErrorState({
  title = "Something went wrong",
  message,
  requestId,
  onRetry,
  className,
}: ErrorStateProps) {
  return (
    <div
      role="alert"
      className={cn(
        "p-4 bg-rose-950/30 border border-rose-800/50 rounded-2xl flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 text-rose-200",
        className
      )}
    >
      <div className="flex items-start gap-3">
        <div className="p-2 rounded-xl bg-rose-900/50 text-rose-300 shrink-0 mt-0.5 sm:mt-0">
          <AlertCircle className="w-5 h-5" />
        </div>
        <div>
          <h4 className="text-sm font-semibold text-rose-100">{title}</h4>
          <p className="text-xs text-rose-300/90 mt-0.5 leading-relaxed">{message}</p>
          {requestId && (
            <p className="text-[10px] font-mono text-rose-400/80 mt-1">
              Request ID: {requestId}
            </p>
          )}
        </div>
      </div>
      {onRetry && (
        <Button
          variant="danger"
          size="sm"
          onClick={onRetry}
          leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
          className="shrink-0 self-end sm:self-auto"
        >
          Retry
        </Button>
      )}
    </div>
  );
}
