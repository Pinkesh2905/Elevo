import os

path = r'c:\Projects\4thSemProject\Elevo\elevo\templates\base.html'
with open(path, 'r', encoding='utf-8', newline='') as f:
    content = f.read()

# Refine User Dropdown
new_dropdown = """                    <div id="user-dropdown" class="hidden absolute right-0 mt-4 w-72 rounded-2xl dropdown-animate z-[200] overflow-hidden">
                        <div class="p-6 bg-gradient-to-br from-slate-900/50 to-slate-950/50 border-b border-white/5 relative">
                            <div class="absolute top-0 right-0 p-4 opacity-10">
                                <i class="ri-shield-user-line text-4xl text-cyan-500"></i>
                            </div>
                            <p class="text-[10px] font-black text-cyan-500 uppercase tracking-widest mb-1.5 flex items-center gap-2">
                                <span class="w-1 h-1 rounded-full bg-cyan-500"></span> Authorized Protocol
                            </p>
                            <p class="text-base font-black text-white truncate">{{ user.username }}</p>
                            {% if request.is_premium %}
                                <div class="mt-3 flex items-center gap-2 px-2.5 py-1 rounded-lg bg-cyan-500/10 border border-cyan-500/20 w-fit">
                                    <i class="ri-vip-diamond-fill text-[10px] text-cyan-400"></i>
                                    <span class="text-[9px] font-black text-cyan-400 uppercase tracking-widest">Premium Entity</span>
                                </div>
                            {% endif %}
                        </div>
                        <div class="p-3 grid grid-cols-1 gap-1">
                            <a href="{% url 'users:profile' %}" class="flex items-center justify-between px-4 py-3 rounded-xl hover:bg-white/5 transition-all group">
                                <div class="flex items-center gap-3">
                                    <div class="w-9 h-9 rounded-lg bg-cyan-500/10 flex items-center justify-center text-cyan-400 group-hover:scale-110 transition-transform">
                                        <i class="ri-user-settings-line"></i>
                                    </div>
                                    <div>
                                        <p class="text-sm font-bold text-slate-200 group-hover:text-white">Mastery Profile</p>
                                        <p class="text-[10px] text-slate-500 font-medium">Digital identity meta-data</p>
                                    </div>
                                </div>
                                <i class="ri-arrow-right-s-line text-slate-600 group-hover:text-cyan-400"></i>
                            </a>
                            <a href="{% url 'chat:inbox' %}" class="flex items-center justify-between px-4 py-3 rounded-xl hover:bg-white/5 transition-all group">
                                <div class="flex items-center gap-3">
                                    <div class="w-9 h-9 rounded-lg bg-emerald-500/10 flex items-center justify-center text-emerald-400 group-hover:scale-110 transition-transform">
                                        <i class="ri-question-answer-line"></i>
                                    </div>
                                    <div>
                                        <p class="text-sm font-bold text-slate-200 group-hover:text-white">Neural Hub</p>
                                        <p class="text-[10px] text-slate-500 font-medium">Communication channel</p>
                                    </div>
                                </div>
                                <i class="ri-arrow-right-s-line text-slate-600 group-hover:text-emerald-400"></i>
                            </a>
                            <a href="{% url 'mock_interview:my_mock_interviews' %}" class="flex items-center justify-between px-4 py-3 rounded-xl hover:bg-white/5 transition-all group">
                                <div class="flex items-center gap-3">
                                    <div class="w-9 h-9 rounded-lg bg-violet-500/10 flex items-center justify-center text-violet-400 group-hover:scale-110 transition-transform">
                                        <i class="ri-history-line"></i>
                                    </div>
                                    <div>
                                        <p class="text-sm font-bold text-slate-200 group-hover:text-white">Session Matrix</p>
                                        <p class="text-[10px] text-slate-500 font-medium">Historical performance</p>
                                    </div>
                                </div>
                                <i class="ri-arrow-right-s-line text-slate-600 group-hover:text-violet-400"></i>
                            </a>
                        </div>
                        <div class="p-3 border-t border-white/5 bg-slate-950/30">
                            <form method="POST" action="{% url 'logout' %}">
                                {% csrf_token %}
                                <button type="submit" class="w-full flex items-center gap-3 px-4 py-3 rounded-xl hover:bg-rose-500/10 text-sm font-bold text-slate-400 hover:text-rose-400 transition-all group">
                                    <div class="w-9 h-9 rounded-lg bg-white/5 flex items-center justify-center group-hover:bg-rose-500/10">
                                        <i class="ri-logout-box-r-line"></i>
                                    </div>
                                    Terminate Session
                                </button>
                            </form>
                        </div>
                    </div>"""

# Find the old dropdown and replace it
import re
dropdown_pattern = re.compile(r'<div id="user-dropdown".*?Sign Protocol Out\s*</button>\s*</form>\s*</div>\s*</div>', re.DOTALL)
content = dropdown_pattern.sub(new_dropdown, content)

# Refine Search Bar
old_search = """            <!-- Global Search -->
            <form method="GET" action="{% url 'search' %}" class="hidden md:flex items-center ml-6 mr-4">
                <div class="relative w-72 lg:w-80">
                    <i class="ri-search-line absolute left-3 top-1/2 -translate-y-1/2 text-slate-500"></i>
                    <input
                        type="text"
                        name="q"
                        value="{{ request.GET.q|default_if_none:'' }}"
                        placeholder="Search users or posts..."
                        class="w-full h-10 pl-10 pr-4 rounded-full bg-slate-900/60 border border-white/10 text-sm text-slate-200 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/40 focus:border-cyan-500/40 transition-all"
                    >
                </div>
            </form>"""

new_search = """            <!-- Global Search -->
            <form method="GET" action="{% url 'search' %}" class="hidden md:flex items-center ml-8 group">
                <div class="relative w-64 lg:w-72">
                    <i class="ri-search-2-line absolute left-4 top-1/2 -translate-y-1/2 text-slate-500 group-focus-within:text-cyan-400 transition-colors"></i>
                    <input
                        type="text"
                        name="q"
                        value="{{ request.GET.q|default_if_none:'' }}"
                        placeholder="Scan protocols..."
                        class="w-full h-10 pl-11 pr-4 rounded-full bg-slate-950/40 border border-white/5 text-[13px] text-slate-200 placeholder:text-slate-600 focus:outline-none focus:ring-1 focus:ring-cyan-500/30 focus:bg-slate-950/80 transition-all"
                    >
                    <div class="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-1 opacity-0 group-focus-within:opacity-100 transition-opacity">
                        <kbd class="px-1.5 py-0.5 rounded border border-white/10 bg-white/5 text-[10px] font-black text-slate-500">ESC</kbd>
                    </div>
                </div>
            </form>"""

content = content.replace(old_search, new_search)

# Tighten Navigation
content = content.replace('text-sm font-bold text-slate-400 hover:text-white transition-all rounded-full hover:bg-white/5', 'text-[13px] font-bold text-slate-400 hover:text-white transition-all px-4 py-2 hover:bg-white/5 rounded-full')

with open(path, 'w', encoding='utf-8', newline='') as f:
    f.write(content)

print("Success")
