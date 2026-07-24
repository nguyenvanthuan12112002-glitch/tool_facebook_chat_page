with open(r'd:\tool_facebook_chat_page\frontend\src\components\PageSyncCard.tsx', 'r', encoding='utf-8') as f:
    lines = f.readlines()

balance = 0
for idx, line in enumerate(lines, 1):
    opens = line.count('{')
    closes = line.count('}')
    balance += opens - closes

print(f"Total lines: {len(lines)}")
print(f"Final net brace balance (should be 0): {balance}")
