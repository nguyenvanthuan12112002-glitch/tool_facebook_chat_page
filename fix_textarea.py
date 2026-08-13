import re
import os

tsx_path = "frontend/src/components/PageSyncCard.tsx"
with open(tsx_path, "r", encoding="utf-8") as f:
    tsx = f.read()

# 1. Add textareaRef
tsx = tsx.replace(
    'const fileInputRef = useRef<HTMLInputElement>(null);',
    'const fileInputRef = useRef<HTMLInputElement>(null);\n  const textareaRef = useRef<HTMLTextAreaElement>(null);'
)

# 2. Add useEffect for auto-resizing
use_effect_code = """
  // Auto-resize textarea when replyText changes (e.g. cleared after send)
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = '36px';
      if (replyText) {
         textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 100) + 'px';
      }
    }
  }, [replyText]);
"""
tsx = tsx.replace(
    '// Scroll to bottom when thread or messages change',
    use_effect_code + '\n  // Scroll to bottom when thread or messages change'
)

# 3. Add ref to textarea and simplify onChange
old_textarea = """                      <textarea
                        rows={1}
                        className={styles.messengerInput}
                        placeholder={is24hBlocked ? "Phản hồi bị khóa (Quá hạn 24h)" : "Aa"}
                        value={replyText}
                        onChange={(e) => {
                          setReplyText(e.target.value);
                          e.target.style.height = '36px';
                          e.target.style.height = Math.min(e.target.scrollHeight, 100) + 'px';
                        }}
                        disabled={is24hBlocked || isSending}
                      />"""

new_textarea = """                      <textarea
                        ref={textareaRef}
                        rows={1}
                        className={styles.messengerInput}
                        placeholder={is24hBlocked ? "Phản hồi bị khóa (Quá hạn 24h)" : "Aa"}
                        value={replyText}
                        onChange={(e) => setReplyText(e.target.value)}
                        disabled={is24hBlocked || isSending}
                      />"""

if old_textarea in tsx:
    tsx = tsx.replace(old_textarea, new_textarea)
else:
    # try regex approach if exact string matching fails due to line endings
    print("Warning: Exact textarea replacement failed, using regex.")
    tsx = re.sub(
        r'<textarea[^>]+onChange=\{\(e\) => \{[^}]+\}\}[^>]+/>',
        new_textarea,
        tsx,
        flags=re.DOTALL
    )

with open(tsx_path, "w", encoding="utf-8") as f:
    f.write(tsx)

css_path = "frontend/src/components/PageSyncCard.module.css"
with open(css_path, "r", encoding="utf-8") as f:
    css = f.read()

# Reduce gap in messengerInputBar
css = re.sub(
    r'(\.messengerInputBar \{[^\}]+?gap:\s*)8px;',
    r'\g<1>4px;',
    css
)
css = re.sub(
    r'(\.messengerInputBar \{[^\}]+?padding:\s*)8px 12px;',
    r'\g<1>6px 8px;',
    css
)

# Reduce padding in iconButton
css = re.sub(
    r'(\.iconButton \{[^\}]+?padding:\s*)8px;',
    r'\g<1>4px;',
    css
)

with open(css_path, "w", encoding="utf-8") as f:
    f.write(css)

print("Updates applied.")
