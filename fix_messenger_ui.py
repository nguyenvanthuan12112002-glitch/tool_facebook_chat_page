import re
import os

css_path = "frontend/src/components/PageSyncCard.module.css"
tsx_path = "frontend/src/components/PageSyncCard.tsx"

with open(css_path, "r", encoding="utf-8") as f:
    css = f.read()

# Fix .bubble
css = re.sub(
    r"\.bubble \{[^}]+\}",
    ".bubble {\n  max-width: 70%;\n  padding: 8px 14px;\n  border-radius: 18px;\n  font-size: 15px;\n  line-height: 1.4;\n  word-wrap: break-word;\n  box-sizing: border-box;\n}",
    css
)

# Fix .bubbleInbound
css = re.sub(
    r"\.bubbleInbound \{[^}]+\}",
    ".bubbleInbound {\n  align-self: flex-start;\n  background: #303030;\n  color: white;\n  border-bottom-left-radius: 4px;\n}",
    css
)

# Fix .bubbleOutbound
css = re.sub(
    r"\.bubbleOutbound \{[^}]+\}",
    ".bubbleOutbound {\n  align-self: flex-end;\n  background: #0084ff;\n  color: white;\n  border-bottom-right-radius: 4px;\n}",
    css
)

# Fix .messengerInputBar
css = re.sub(
    r"\.messengerInputBar \{[^}]+\}",
    ".messengerInputBar {\n  display: flex;\n  align-items: center;\n  gap: 8px;\n  padding: 8px 12px;\n  background: black;\n  width: 100%;\n}",
    css
)

# Fix .inputContainer
css = re.sub(
    r"\.inputContainer \{[^}]+\}",
    ".inputContainer {\n  position: relative;\n  flex-grow: 1;\n  display: flex;\n  align-items: center;\n  background: rgba(255, 255, 255, 0.15);\n  border-radius: 20px;\n  padding: 4px 12px;\n  min-height: 36px;\n}",
    css
)

# Fix .messengerInput
css = re.sub(
    r"\.messengerInput \{[^}]+\}",
    ".messengerInput {\n  flex-grow: 1;\n  background: none;\n  border: none;\n  color: white;\n  font-size: 15px;\n  outline: none;\n  padding: 4px 0;\n}",
    css
)

# Fix .chatBody
css = re.sub(
    r"\.chatBody \{[^}]+\}",
    ".chatBody {\n  flex: 1;\n  padding: 16px;\n  overflow-y: auto;\n  display: flex;\n  flex-direction: column;\n  background: black;\n}",
    css
)

with open(css_path, "w", encoding="utf-8") as f:
    f.write(css)

print("CSS updated.")
