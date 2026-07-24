import re

file_path = r'd:\tool_facebook_chat_page\frontend\src\components\PageSyncCard.tsx'
with open(file_path, 'r', encoding='utf-8') as f:
    code = f.read()

lines = code.split('\n')
stack = []

for line_no, line in enumerate(lines, 1):
    clean = re.sub(r'//.*', '', line)
    clean = re.sub(r'/\*.*?\*/', '', clean)
    clean = re.sub(r'".*?"|\'.*?\'|`.*?`', '', clean)
    
    tokens = re.findall(r'</?[a-zA-Z0-9_-]+|</?>|[{}]|\(|\)', clean)
    for tok in tokens:
        if tok in ['{', '(', '<>', '<div']:
            stack.append((line_no, tok))
        elif tok == '}':
            if stack and stack[-1][1] == '{':
                stack.pop()
            else:
                last_item = stack[-1] if stack else 'None'
                print("Mismatch } at line " + str(line_no) + ". Expected match for " + str(last_item))
        elif tok == ')':
            if stack and stack[-1][1] == '(':
                stack.pop()
            else:
                last_item = stack[-1] if stack else 'None'
                print("Mismatch ) at line " + str(line_no) + ". Expected match for " + str(last_item))
        elif tok in ['</>', '</div>']:
            if stack and stack[-1][1] in ['<>', '<div']:
                stack.pop()
            else:
                last_item = stack[-1] if stack else 'None'
                print("Mismatch " + tok + " at line " + str(line_no) + ". Expected match for " + str(last_item))

print("Analysis finished. Remaining unclosed tokens in stack (count: " + str(len(stack)) + "):")
for item in stack:
    print(item)
