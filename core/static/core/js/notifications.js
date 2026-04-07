(function() {
  const NOTIFICATION_SOUND_B64 = "data:audio/wav;base64,UklGRl9vT19XQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YTdvT18AZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAGQAZABkAA==";

  class ElevoNotificationManager {
    constructor() {
      this.stream = null;
      this.lastId = 0;
      this.isMuted = localStorage.getItem('chat_muted') === 'true';
      this.audio = new Audio(NOTIFICATION_SOUND_B64);
      this.audio.volume = 0.4;
      
      this.init();
    }

    init() {
      if (!window.EventSource) return;
      this.connect();
      this.setupSoundToggles();
      
      // Request permission on first user interaction if not determined
      document.addEventListener('click', () => {
        if (Notification.permission === 'default') {
          Notification.requestPermission();
        }
      }, { once: true });
    }

    connect() {
      if (this.stream) this.stream.close();
      
      this.stream = new EventSource(`/chat/notifications/stream/?last_id=${this.lastId}`);
      
      this.stream.addEventListener('notification', (e) => {
        const data = JSON.parse(e.data);
        this.lastId = data.message_id;
        this.handleNewMessage(data);
      });

      this.stream.addEventListener('unread_update', (e) => {
        const data = JSON.parse(e.data);
        this.updateGlobalBadge(data.total);
        this.updateThreadBadges(data.threads);
      });

      this.stream.onerror = () => {
        this.stream.close();
        setTimeout(() => this.connect(), 5000);
      };
    }

    handleNewMessage(data) {
      // Don't show notification if user is currently looking at this specific thread
      const activeContainer = document.getElementById('messagesContainer');
      if (activeContainer && activeContainer.dataset.threadId == data.thread_id && !document.hidden) {
        return;
      }

      this.playNotificationSound();
      this.showDesktopNotification(data);
    }

    showDesktopNotification(data) {
      if (Notification.permission === 'granted') {
        const n = new Notification(`New message from ${data.sender_name}`, {
          body: data.content_snippet,
          icon: '/static/core/images/logo_icon.png', // Fallback icon path
          tag: `chat-thread-${data.thread_id}` // Group notifications by thread
        });

        n.onclick = () => {
          window.focus();
          window.location.href = `/chat/${data.thread_id}/`;
        };
      }
    }

    playNotificationSound() {
      if (!this.isMuted) {
        this.audio.play().catch(e => console.log("Audio playback held by browser policy"));
      }
    }

    updateGlobalBadge(count) {
      const badges = document.querySelectorAll('#navUnreadBadge');
      badges.forEach(badge => {
        if (count > 0) {
          badge.textContent = count > 99 ? '99' : count;
          badge.classList.remove('hidden');
          badge.classList.add('flex');
        } else {
          badge.classList.add('hidden');
        }
      });
    }

    updateThreadBadges(threadMap) {
      // 1. Update Sidebar Badges (in thread.html) and move to top
      const sidebarContainer = document.querySelector('.chat-sidebar');
      const sidebarLinks = document.querySelectorAll('.sidebar-thread');
      
      sidebarLinks.forEach(link => {
        const threadIdMatch = link.href.match(/\/chat\/(\d+)\//);
        if (threadIdMatch) {
          const tid = threadIdMatch[1];
          const badge = link.querySelector('.absolute.-right-1.-top-1');
          
          if (threadMap[tid]) {
             if (!badge) {
               link.querySelector('.relative.shrink-0').insertAdjacentHTML('beforeend', '<span class="absolute -right-1 -top-1 h-3 w-3 rounded-full border-2 border-slate-950 bg-sky-400"></span>');
             }
             // Move to top of sidebar
             if (sidebarContainer && sidebarContainer.firstChild !== link) {
               sidebarContainer.prepend(link);
             }
          } else if (badge) {
             badge.remove();
          }
        }
      });

      // 2. Update Inbox List Badges (in inbox.html) and move to top
      const inboxContainer = document.getElementById('threadListContainer');
      const inboxThreadItems = document.querySelectorAll('.thread-item');
      
      inboxThreadItems.forEach(item => {
        const threadIdMatch = item.href.match(/\/chat\/(\d+)\//);
        if (threadIdMatch) {
          const tid = threadIdMatch[1];
          let badge = item.querySelector('.unread-badge');
          
          if (threadMap[tid]) {
            // Update/Add badge
            if (!badge) {
              const infoBlock = item.querySelector('.flex.items-center.justify-between:last-child');
              infoBlock.insertAdjacentHTML('beforeend', `<span class="unread-badge flex-shrink-0 animate-in zoom-in duration-300">${threadMap[tid]}</span>`);
            } else {
              badge.textContent = threadMap[tid];
            }
            
            // Move to top of inbox
            if (inboxContainer && inboxContainer.firstChild !== item) {
              inboxContainer.prepend(item);
            }
          } else if (badge) {
            badge.remove();
          }
        }
      });
    }

    setupSoundToggles() {
      document.body.addEventListener('click', (e) => {
        const toggle = e.target.closest('#soundToggleBtn');
        if (toggle) {
          this.isMuted = !this.isMuted;
          localStorage.setItem('chat_muted', this.isMuted);
          this.updateSoundIcon(toggle);
        }
      });

      // Initial icon state
      const toggles = document.querySelectorAll('#soundToggleBtn');
      toggles.forEach(t => this.updateSoundIcon(t));
    }

    updateSoundIcon(btn) {
      const icon = btn.querySelector('i');
      if (this.isMuted) {
        icon.className = 'ri-volume-mute-line';
        btn.classList.add('text-slate-500');
        btn.classList.remove('text-sky-400');
        btn.title = 'Enable Notification Sounds';
      } else {
        icon.className = 'ri-volume-up-line';
        btn.classList.remove('text-slate-500');
        btn.classList.add('text-sky-400');
        btn.title = 'Mute Notification Sounds';
      }
    }
  }

  // Self-initialize
  window.elevoNotifications = new ElevoNotificationManager();
})();
