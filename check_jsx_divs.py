with open(r'd:\tool_facebook_chat_page\frontend\src\components\PageSyncCard.tsx', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Remove line 2243
lines.pop(2242) # 0-indexed line 2243

stack = []
for idx, line in enumerate(lines):
    pos = 0
    while pos < len(line):
        if line[pos:pos+4] == '<div':
            end_tag = line.find('>', pos)
            if end_tag != -1 and line[end_tag-1:end_tag+1] == '/>':
                pos = end_tag + 1
                continue
            stack.append((idx + 1, line.strip()[:40]))
            pos += 4
        elif line[pos:pos+6] == '</div>':
            if stack:
                opened_line, opened_code = stack.pop()
            else:
                print(f"Extra closing </div> at line {idx+1}")
            pos += 6
        else:
            pos += 1

print("\nRemaining unclosed divs:")
for line_num, code in stack:
    print(f"Line {line_num}: {code}")
