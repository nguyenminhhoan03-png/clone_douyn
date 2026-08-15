import re

with open('gui.py', 'r', encoding='utf-8') as f:
    content = f.read()

replacements = {
    '"#e74c3c"': 'DANGER',
    '"#c0392b"': '"#DC2626"',  # DANGER_HOVER
    '"#2ecc71"': 'SUCCESS',
    '"#27ae60"': '"#059669"',  # SUCCESS_HOVER
    '"#f39c12"': 'WARNING',
    '"#e67e22"': '"#D97706"',  # WARNING_HOVER
    '"#9b59b6"': 'ACCENT',
    '"#8e44ad"': 'ACCENT_HOVER',
    '"#3498db"': 'ACCENT',
    '"#2980b9"': 'ACCENT',
    '"#1E293B"': 'BG_CARD',
    '"#3B82F6"': 'ACCENT'
}

for old, new in replacements.items():
    content = content.replace(old, new)
    
with open('gui.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Theme applied successfully!")
