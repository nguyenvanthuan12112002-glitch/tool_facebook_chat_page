import sys
import os

css_file = r'D:\tool_facebook_chat_page\frontend\src\components\PageSyncCard.module.css'

with open(css_file, 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

# Truncate at line 1417 (0-indexed 1416)
lines = lines[:1417]

modal_css = """
/* MODAL STYLES */
.modalOverlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.modalContent {
  background: #1e1e24;
  border: 1px solid var(--border-glass);
  border-radius: 12px;
  width: 400px;
  max-width: 90%;
  padding: 20px;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5);
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.modalHeader {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 16px;
  font-weight: 700;
  color: white;
  margin-bottom: 8px;
}
.modalCloseBtn {
  background: none;
  border: none;
  color: #9ca3af;
  cursor: pointer;
  font-size: 20px;
  transition: 0.2s;
}
.modalCloseBtn:hover {
  color: white;
}
"""

with open(css_file, 'w', encoding='utf-8') as f:
    f.writelines(lines)
    f.write(modal_css)

print("CSS fixed")
