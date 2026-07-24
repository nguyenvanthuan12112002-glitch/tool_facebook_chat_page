"use client";

import { useEffect } from "react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log the error to an external error reporting service
    console.error(error);
  }, [error]);

  return (
    <div style={{ padding: '20px', background: '#ffebee', color: '#b71c1c', borderRadius: '8px', maxWidth: '800px', margin: '40px auto', fontFamily: 'sans-serif' }}>
      <h2>🚨 Phát hiện lỗi giao diện (Client-side Crash)</h2>
      <p>Ứng dụng đã bị lỗi. Vui lòng chụp màn hình thông báo này gửi cho AI để sửa lỗi:</p>
      <pre style={{ background: '#fff', padding: '16px', borderRadius: '4px', overflowX: 'auto', border: '1px solid #ffcdd2', fontSize: '14px', whiteSpace: 'pre-wrap' }}>
        {error.message}
        {"\n\n"}
        {error.stack}
      </pre>
      <button
        style={{ marginTop: '20px', padding: '10px 20px', background: '#d32f2f', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}
        onClick={() => reset()}
      >
        Thử tải lại (Try again)
      </button>
    </div>
  );
}
