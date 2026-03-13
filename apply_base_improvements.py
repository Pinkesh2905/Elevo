import os

path = r'c:\Projects\4thSemProject\Elevo\elevo\templates\base.html'
with open(path, 'r', encoding='utf-8', newline='') as f:
    content = f.read()

# Refine CSS Variables
content = content.replace(
    '            --accent-sky: #0ea5e9;\r\n        }',
    '            --accent-sky: #0ea5e9;\r\n            --accent-violet: #818cf8;\r\n        }'
)

# body letter spacing
content = content.replace(
    '            overflow-x: hidden;\r\n        }',
    '            overflow-x: hidden;\r\n            letter-spacing: -0.01em;\r\n        }'
)

# brand font letter spacing
content = content.replace(
    "        .brand-font { font-family: 'Outfit', sans-serif; }",
    "        .brand-font { font-family: 'Outfit', sans-serif; letter-spacing: -0.02em; }"
)

# glass-elevated saturation and blur
content = content.replace(
    '            background: rgba(15, 23, 42, 0.7);\r\n            backdrop-filter: blur(24px) saturate(160%);\r\n            -webkit-backdrop-filter: blur(24px) saturate(160%);\r\n            border: 1px solid rgba(255, 255, 255, 0.08);',
    '            background: rgba(15, 23, 42, 0.75);\r\n            backdrop-filter: blur(24px) saturate(180%);\r\n            -webkit-backdrop-filter: blur(24px) saturate(180%);\r\n            border: 1px solid rgba(255, 255, 255, 0.08);\r\n            box-shadow: 0 4px 24px -1px rgba(0, 0, 0, 0.2);'
)

# navbar-blur background and blur
content = content.replace(
    '            background: rgba(2, 6, 23, 0.85);\r\n            backdrop-filter: blur(20px) saturate(180%);\r\n            -webkit-backdrop-filter: blur(20px) saturate(180%);\r\n            border-bottom: 1px solid rgba(255, 255, 255, 0.05);',
    '            background: rgba(2, 6, 23, 0.7);\r\n            backdrop-filter: blur(16px) saturate(120%);\r\n            -webkit-backdrop-filter: blur(16px) saturate(120%);\r\n            border-bottom: 1px solid rgba(255, 255, 255, 0.05);'
)

# Brand link gap
content = content.replace(
    '<a href="{% url \'home\' %}" class="flex items-center gap-3 group">',
    '<a href="{% url \'home\' %}" class="flex items-center gap-2.5 group">'
)

# Brand logo pulse and gradient
content = content.replace(
    '<stop offset="1" stop-color="#34d399"/>',
    '<stop offset="0.5" stop-color="#818cf8"/>\r\n                                <stop offset="1" stop-color="#34d399"/>'
)

# radialGradient stop-color
content = content.replace(
    '<stop offset="0" stop-color="#164e63" stop-opacity="0.6"/>',
    '<stop offset="0" stop-color="#22d3ee" stop-opacity="0.2"/>'
)

# brand font size and class
content = content.replace(
    '<span class="text-2xl font-black text-white brand-font tracking-tight group-hover:text-cyan-400 transition-colors">Elevo</span>',
    '<span class="text-xl font-black text-white brand-font tracking-tight group-hover:text-cyan-400 transition-all duration-300">Elevo</span>'
)

with open(path, 'w', encoding='utf-8', newline='') as f:
    f.write(content)

print("Success")
