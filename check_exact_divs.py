import re

with open(r'd:\tool_facebook_chat_page\frontend\src\components\PageSyncCard.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')

stack = []

tag_re = re.compile(r'</?div\b[^>]*>')

for line_idx, line in enumerate(lines, 1):
    # Remove strings to avoid false matches inside text
    line_clean = re.sub(r'".*?"|\'.*?\'|`.*?`', '', line)
    for match in tag_re.finditer(line_clean):
        tag = match.group(0)
        if tag.startswith('</div'):
            if stack:
                opened_line, opened_tag = stack.pop()
            else:
                print(f"EXTRA CLOSING </div> at line {line_idx}: {line.strip()}")
        elif not tag.endswith('/>'):
            stack.append((line_idx, line.strip()))

print("\nUNCLOSED DIVS AT END OF FILE:")
for line_idx, code in stack:
    print(f"Line {line_idx:4d}: {code}")
