import os

path = r'c:\Projects\4thSemProject\Elevo\elevo\templates\base.html'
with open(path, 'r', encoding='utf-8', newline='') as f:
    content = f.read()

# Optimize spawnSymbol
old_spawn = """            function spawnSymbol() {
                if(!container) return;
                const s = document.createElement('div');
                s.className = 'symbol-float';
                s.textContent = symbols[Math.floor(Math.random() * symbols.length)];
                s.style.left = Math.random() * 100 + 'vw';
                s.style.top = '110vh';
                s.style.fontSize = Math.random() * 8 + 10 + 'px';
                s.style.color = ['#22d3ee', '#34d399', '#818cf8'][Math.floor(Math.random() * 3)];
                container.appendChild(s);
                
                gsap.to(s, {
                    y: '-120vh',
                    x: (Math.random() - 0.5) * 100,
                    rotation: Math.random() * 360,
                    duration: Math.random() * 15 + 15,
                    ease: "none",
                    onComplete: () => s.remove()
                });
            }"""

new_spawn = """            function spawnSymbol() {
                if(!container || document.visibilityState === 'hidden') return;
                const s = document.createElement('div');
                s.className = 'symbol-float';
                s.textContent = symbols[Math.floor(Math.random() * symbols.length)];
                s.style.left = Math.random() * 100 + 'vw';
                s.style.top = '105vh';
                s.style.fontSize = Math.random() * 6 + 10 + 'px';
                s.style.color = ['#22d3ee', '#34d399', '#818cf8'][Math.floor(Math.random() * 3)];
                s.style.filter = `blur(${Math.random() * 2}px)`;
                container.appendChild(s);
                
                gsap.to(s, {
                    y: '-115vh',
                    x: (Math.random() - 0.5) * 150,
                    rotation: Math.random() * 360,
                    duration: Math.random() * 20 + 20,
                    ease: "sine.inOut",
                    opacity: 0,
                    delay: Math.random() * 0.5,
                    onComplete: () => s.remove()
                });
            }"""

content = content.replace(old_spawn, new_spawn)

# Optimize Vanta parameters
content = content.replace('points: 10.00,', 'points: 12.00,')
content = content.replace('maxDistance: 20.00,', 'maxDistance: 18.00,')
content = content.replace('spacing: 18.00', 'spacing: 16.00')

with open(path, 'w', encoding='utf-8', newline='') as f:
    f.write(content)

print("Success")
