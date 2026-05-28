// ── Notification Dropdown (Gmail-style) ──────────────
let notifOpen = false;
let notifLoaded = false;

function toggleNotifDropdown() {
  const panel = document.getElementById('notif-panel');
  if (!panel) return;

  notifOpen = !notifOpen;
  panel.classList.toggle('open', notifOpen);

  if (notifOpen && !notifLoaded) {
    loadNotifDropdown();
  }
}

// Close dropdown when clicking outside
document.addEventListener('click', function(e) {
  const wrap = document.getElementById('notif-wrap');
  if (wrap && !wrap.contains(e.target)) {
    const panel = document.getElementById('notif-panel');
    if (panel) panel.classList.remove('open');
    notifOpen = false;
  }
});

async function loadNotifDropdown() {
  const list = document.getElementById('notif-panel-list');
  const unreadLabel = document.getElementById('notif-unread-label');
  if (!list) return;

  try {
    const res = await fetch('/api/notif-recent');
    const data = await res.json();

    notifLoaded = true;

    // Update unread count label
    const unread = data.filter(n => !n.is_read).length;
    if (unreadLabel) {
      unreadLabel.textContent = unread > 0 ? `${unread} belum dibaca` : 'Semua dibaca';
      unreadLabel.style.background = unread > 0 ? '#4361ee' : '#94a3b8';
    }

    if (data.length === 0) {
      list.innerHTML = `
        <div class="notif-empty">
          <svg width="36" height="36" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
            <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
          </svg>
          Belum ada notifikasi
        </div>`;
      return;
    }

    const notifUrl = window.location.pathname.startsWith('/dc') ? '/dc/notifikasi' : '/notifikasi';
    
    list.innerHTML = data.map(n => {
      let iconHtml = '';
      if (n.bukti) {
        iconHtml = `<img src="/static/uploads/${n.bukti}" alt="Bukti" style="width:100%; height:100%; object-fit:cover; border-radius:6px;">`;
      } else {
        iconHtml = `<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
            <line x1="12" y1="9" x2="12" y2="13"/>
            <line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>`;
      }
      
      return `
      <div onclick="openNotifModal('${n.id}', '${n.jenis_benda}', '${n.camera_name}', '${n.waktu}', '${n.bukti||''}')" class="notif-item-drop ${!n.is_read ? 'unread' : ''}" style="cursor:pointer;">
        <div class="notif-item-dot ${n.is_read ? 'read' : ''}"></div>
        <div class="notif-item-icon ${n.is_read ? 'read-icon' : ''}" style="padding:0; overflow:hidden; display:flex; align-items:center; justify-content:center; background:#f1f5f9;">
          ${iconHtml}
        </div>
        <div class="notif-item-body">
          <div class="notif-item-title">⚠ ${n.jenis_benda} terdeteksi</div>
          <div class="notif-item-sub">${n.camera_name === '—' ? 'Simulasi CCTV' : n.camera_name}</div>
          <div class="notif-item-time">${n.waktu}</div>
        </div>
      </div>
    `}).join('');

  } catch (e) {
    if (list) list.innerHTML = '<div class="notif-loading">Gagal memuat notifikasi.</div>';
  }
}

// ── Notification Count Badge ───────────────────────
async function loadNotifCount() {
  try {
    const res = await fetch('/api/notif-count');
    const data = await res.json();
    const badge = document.getElementById('notif-count-badge');

    if (badge) {
      if (data.count > 0) {
        badge.textContent = data.count > 99 ? '99+' : data.count;
        badge.style.display = 'flex';
      } else {
        badge.style.display = 'none';
      }
    }

    // Legacy: nav badge in sidebar
    document.querySelectorAll('.notif-badge').forEach(b => {
      if (data.count > 0) {
        b.textContent = data.count;
        b.style.display = 'inline-flex';
      } else {
        b.style.display = 'none';
      }
    });
  } catch (e) {
    // Silent fail
  }
}

// ── Init ───────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadNotifCount();
  setInterval(loadNotifCount, 30000);

  // Reset loaded state on each page load so dropdown refetches
  notifLoaded = false;

  // ── Date/Time realtime ───────────────────────────
  const clockEl = document.getElementById('realtime-clock');
  if (clockEl) {
    function updateClock() {
      const now = new Date();
      clockEl.textContent = now.toLocaleString('id-ID', {
        weekday: 'long', year: 'numeric',
        month: 'long', day: 'numeric',
        hour: '2-digit', minute: '2-digit', second: '2-digit'
      });
    }
    updateClock();
    setInterval(updateClock, 1000);
  }

  // ── Flash message auto-dismiss ───────────────────
  document.querySelectorAll('.alert[data-dismiss]').forEach(el => {
    setTimeout(() => {
      el.style.opacity = '0';
      el.style.transition = 'opacity .4s';
      setTimeout(() => el.remove(), 400);
    }, 4000);
  });
});

// ── Spin keyframe (for loading icon) ──────────────
const style = document.createElement('style');
style.textContent = `
@keyframes spin { to { transform: rotate(360deg); } }
@keyframes popScale { 0% { transform: scale(0.9); opacity: 0; } 100% { transform: scale(1); opacity: 1; } }
`;
document.head.appendChild(style);

// ── Notif Modal (Mobile-like Popup) ───────────────
window.openNotifModal = function(id, jenis, camera, waktu, bukti) {
  // Tandai sudah dibaca di backend
  fetch(`/api/notif-read/${id}`, { method: 'POST' });
  loadNotifCount(); // perbarui badge

  // Buat modal overlay jika belum ada
  let modal = document.getElementById('notif-modal-overlay');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'notif-modal-overlay';
    modal.style.cssText = 'position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(15,23,42,0.8); z-index:9999; display:flex; align-items:center; justify-content:center; padding:20px;';
    
    // Klik area luar untuk nutup
    modal.onclick = function(e) {
      if (e.target === modal) modal.style.display = 'none';
    };
    document.body.appendChild(modal);
  }

  let imgTag = bukti && bukti !== 'null' 
    ? `<img src="/static/uploads/${bukti}" style="width:100%; max-height:50vh; object-fit:contain; border-radius:8px; margin-bottom:16px; background:#000;">` 
    : `<div style="padding:40px; text-align:center; background:#f1f5f9; border-radius:8px; margin-bottom:16px; color:#94a3b8;">Tidak ada bukti gambar</div>`;

  modal.innerHTML = `
    <div style="background:#fff; width:100%; max-width:400px; border-radius:16px; overflow:hidden; box-shadow:0 20px 25px -5px rgba(0,0,0,0.1); animation: popScale 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);">
      <div style="padding:16px 20px; border-bottom:1px solid #e2e8f0; display:flex; justify-content:space-between; align-items:center;">
        <h3 style="margin:0; font-size:1.1rem; color:#0f172a;">Detail Peringatan</h3>
        <button onclick="document.getElementById('notif-modal-overlay').style.display='none'" style="background:none; border:none; cursor:pointer; color:#64748b; padding:0; display:flex;">
          <svg width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </div>
      <div style="padding:20px;">
        ${imgTag}
        <div style="display:flex; align-items:center; gap:8px; margin-bottom:10px;">
          <div style="width:10px; height:10px; background:#ef4444; border-radius:50%; box-shadow: 0 0 8px #ef4444;"></div>
          <span style="font-weight:700; color:#0f172a; font-size:1.1rem;">${jenis} Terdeteksi!</span>
        </div>
        <p style="margin:0 0 6px 18px; font-size:0.9rem; color:#475569;">📍 Kamera: <strong style="color:#0f172a;">${camera === '—' ? 'Simulasi CCTV' : camera}</strong></p>
        <p style="margin:0 0 0 18px; font-size:0.85rem; color:#64748b;">🕒 ${waktu}</p>
      </div>
    </div>
  `;
  modal.style.display = 'flex';
  
  // Tutup dropdown notifikasi agak modal tidak terhalangi atau keramean
  let panel = document.getElementById('notif-panel');
  if (panel) panel.classList.remove('open');
  if (typeof notifOpen !== 'undefined') notifOpen = false;
};

// ── Mobile Sidebar Toggle ─────────────────────────
window.toggleSidebar = function() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebar-overlay');
  
  if (sidebar && overlay) {
    sidebar.classList.toggle('open');
    overlay.classList.toggle('show');
  }
};
