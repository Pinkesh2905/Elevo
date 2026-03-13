import os

path = r'c:\Projects\4thSemProject\Elevo\elevo\templates\base.html'
with open(path, 'rb') as f:
    content = f.read(500)
    print(content)
