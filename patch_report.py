import re

with open('generate_complete_report.py', encoding='utf-8') as f:
    content = f.read()

# Replace all non-ASCII in print statements and labels
# Fix checkmark/cross emojis in the implemented features table
content = content.replace('OK Implemented', 'Implemented')
content = content.replace('Not Implemented', 'Not Implemented')

# Fix emoji in use case diagram actor labels
content = content.replace("'UC Agent / Admin'", "'CS Agent / Admin'")
content = content.replace("'\\U0001f916 System'", "'System'")
content = content.replace("'\\U0001f464 CS Agent'", "'CS Agent'")
content = content.replace("'\\U0001f511 Admin'", "'Admin'")

# Replace the unicode tick in print statement
content = content.replace(
    "print(f\"  \\u2713 All diagrams saved to '{DIAGRAMS_DIR}/' folder.\")",
    "print(f\"  All diagrams saved to '{DIAGRAMS_DIR}/' folder.\")"
)

# Replace all remaining non-ascii characters in string literals
def replace_non_ascii(text):
    result = []
    for char in text:
        if ord(char) > 127:
            # Map specific ones
            mapping = {
                '\u2713': '[OK]', '\u274c': '[X]', '\u2705': '[YES]',
                '\U0001f916': '[SYS]', '\U0001f464': '[USER]', '\U0001f511': '[KEY]',
            }
            result.append(mapping.get(char, ''))
        else:
            result.append(char)
    return ''.join(result)

content = replace_non_ascii(content)

with open('generate_complete_report.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Patch complete.')
