"use client";

import React, { Component, ErrorInfo, ReactNode } from "react";

interface Props {
  children?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
    errorInfo: null
  };

  public static getDerivedStateFromError(error: Error): State {
    // Update state so the next render will show the fallback UI.
    return { hasError: true, error, errorInfo: null };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Uncaught error:", error, errorInfo);
    this.setState({ errorInfo });
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: "20px", background: "#7f1d1d", color: "white", minHeight: "100vh" }}>
          <h2>🚨 Giao diện gặp lỗi (React Rendering Error)</h2>
          <p>Vui lòng chụp màn hình này gửi cho AI:</p>
          <pre style={{ background: "#450a0a", padding: "15px", whiteSpace: "pre-wrap", overflowX: "auto", fontSize: "14px" }}>
            {this.state.error?.toString()}
          </pre>
          <br/>
          <h3>Component Stack:</h3>
          <pre style={{ background: "#450a0a", padding: "15px", whiteSpace: "pre-wrap", overflowX: "auto", fontSize: "12px" }}>
            {this.state.errorInfo?.componentStack}
          </pre>
          <button onClick={() => window.location.reload()} style={{ marginTop: "20px", padding: "10px 20px" }}>
            Tải lại trang
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
