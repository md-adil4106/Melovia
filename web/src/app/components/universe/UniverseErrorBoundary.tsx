"use client";

import React, { Component, ErrorInfo, ReactNode } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onFallback?: () => void;
}

interface State {
  hasError: boolean;
  errorMessage: string | null;
}

export class UniverseErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, errorMessage: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, errorMessage: error.message || "WebGL context error" };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.warn("Caught 3D Universe rendering error:", error, errorInfo);
    if (this.props.onFallback) {
      this.props.onFallback();
    }
  }

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      return (
        <div className="absolute inset-0 flex flex-col items-center justify-center p-6 bg-[#0c0f17] text-center">
          <div className="max-w-md p-5 bg-[#171b26] border border-[#263147] rounded-2xl">
            <AlertTriangle className="w-8 h-8 text-[#d4af37] mx-auto mb-2" />
            <h3 className="text-sm font-semibold text-[#f1f3f7] mb-1">
              3D Acceleration Unavailable
            </h3>
            <p className="text-xs text-[#8c96a8] mb-4">
              {this.state.errorMessage || "Your browser or graphics driver encountered an error creating the 3D WebGL context."}
            </p>
            <button
              type="button"
              onClick={() => this.setState({ hasError: false, errorMessage: null })}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-[#252f44] hover:bg-[#303d58] text-[#d4af37] transition-colors"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Retry 3D Render
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
