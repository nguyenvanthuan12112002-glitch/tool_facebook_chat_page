import re

tsx_path = "frontend/src/components/PageSyncCard.tsx"

with open(tsx_path, "r", encoding="utf-8") as f:
    tsx = f.read()

# Update chatHeader for Message Thread
# Find the chatHeader section and replace the back button
tsx = tsx.replace(
    """<button className={styles.mobileBackBtn} onClick={() => setActiveThread(null)}>
                      <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M15.41 16.59L10.83 12l4.58-4.59L14 6l-6 6 6 6 1.41-1.41z"/></svg>
                      Quay lại
                    </button>""",
    """<button className={styles.mobileBackBtn} onClick={() => setActiveThread(null)} style={{ background: "none", color: "#0084ff", padding: "0 8px 0 0", marginRight: "4px" }}>
                      <svg viewBox="0 0 24 24" width="28" height="28" fill="currentColor"><path d="M15.41 16.59L10.83 12l4.58-4.59L14 6l-6 6 6 6 1.41-1.41z"/></svg>
                    </button>"""
)

# Also update the chatHeaderTitle
tsx = tsx.replace(
    """<div className={styles.chatHeaderTitle} style={{ display: "flex", alignItems: "center", gap: "6px" }}>""",
    """<div className={styles.chatHeaderTitle} style={{ display: "flex", flexDirection: "column" }}>"""
)
tsx = tsx.replace(
    """<div className={styles.chatHeaderSubtitle}>""",
    """<div className={styles.chatHeaderSubtitle} style={{ fontSize: "12px", color: "rgba(255,255,255,0.6)" }}>"""
)


with open(tsx_path, "w", encoding="utf-8") as f:
    f.write(tsx)

print("TSX updated.")
