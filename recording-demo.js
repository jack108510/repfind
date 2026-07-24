(() => {
  'use strict';

  const STORAGE_KEYS = [
    'repfind_agents',
    'repfind_currency',
    'repfind_history',
    'repfind_cart',
    'repfind_session'
  ];

  STORAGE_KEYS.forEach((key) => {
    try {
      localStorage.removeItem(key);
      sessionStorage.removeItem(key);
    } catch (_) {
      // Storage is optional for the recording page.
    }
  });

  Math.random = () => 0.24;
  try {
    localStorage.setItem('repfind_onboarded', '1');
  } catch (_) {
    // Storage is optional for the recording page.
  }
  window.showOnboarding = () => {
    document.getElementById('onboardOverlay')?.classList.remove('show');
  };

  const nativeFetch = window.fetch.bind(window);
  const configuredSearchTerm = String(window.REPFIND_RECORDING_CONFIG?.searchTerm || 'Jordan 4').trim() || 'Jordan 4';
  const escapedSearchTerm = configuredSearchTerm.replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[character]));
  const deterministicReply = {
    action: 'search',
    search_query: configuredSearchTerm,
    reply: `Here are strong local matches for <strong>${escapedSearchTerm}</strong>. Compare the direct-link listings, open an item to review its details, then save a favorite to your haul.`
  };

  window.fetch = (input, init) => {
    const url = typeof input === 'string' ? input : input?.url || String(input || '');
    if (url.includes('n8n.wildeautomations.com/webhook/repfind-chat')) {
      return new Promise((resolve) => {
        window.setTimeout(() => {
          resolve(new Response(JSON.stringify(deterministicReply), {
            status: 200,
            headers: { 'Content-Type': 'application/json' }
          }));
        }, 700);
      });
    }
    return nativeFetch(input, init);
  };

  const style = document.createElement('style');
  style.textContent = `
    #recordingCursor {
      position: fixed;
      top: 0;
      left: 0;
      width: 30px;
      height: 40px;
      z-index: 9999;
      pointer-events: none;
      opacity: 0;
      transform: translate(-3px, -3px);
      transition: left 300ms cubic-bezier(.18,.84,.25,1), top 300ms cubic-bezier(.18,.84,.25,1), opacity 160ms ease;
      will-change: left, top, opacity;
      filter: drop-shadow(0 2px 2px rgba(0,0,0,.55));
    }
    #recordingCursor::before {
      content: '';
      position: absolute;
      width: 0;
      height: 0;
      border-top: 0 solid transparent;
      border-bottom: 26px solid #fff;
      border-right: 18px solid transparent;
      transform: rotate(-18deg);
      transform-origin: 0 0;
      -webkit-clip-path: polygon(0 0, 100% 100%, 45% 76%, 31% 100%);
      clip-path: polygon(0 0, 100% 100%, 45% 76%, 31% 100%);
    }
    #recordingCursor::after {
      content: '';
      position: absolute;
      width: 8px;
      height: 8px;
      border: 3px solid #e8624a;
      border-radius: 999px;
      left: 9px;
      top: 11px;
      opacity: 0;
      transform: scale(.5);
    }
    #recordingCursor.clicked::after {
      animation: recordingClick 420ms ease-out;
    }
    @keyframes recordingClick {
      0% { opacity: .95; transform: scale(.5); }
      65% { opacity: .9; transform: scale(2.6); }
      100% { opacity: 0; transform: scale(3.1); }
    }
  `;
  document.head.appendChild(style);

  const cursor = document.createElement('div');
  cursor.id = 'recordingCursor';
  cursor.setAttribute('aria-hidden', 'true');
  document.addEventListener('DOMContentLoaded', () => document.body.appendChild(cursor));

  const moveCursor = (x, y) => {
    cursor.style.left = `${Math.round(x)}px`;
    cursor.style.top = `${Math.round(y)}px`;
    cursor.style.opacity = '1';
  };

  const pulseCursor = () => {
    cursor.classList.remove('clicked');
    void cursor.offsetWidth;
    cursor.classList.add('clicked');
  };

  // The production page automatically scrolls to each appended chat update.  The recording copy
  // disables that behavior so the scripted cursor-led browse gestures are the only visible scroll.
  const chatArea = document.getElementById('chatArea');
  if (chatArea) chatArea.style.scrollBehavior = 'auto';
  const suppressAutoScroll = () => {};
  window.scrollToBottom = suppressAutoScroll;
  // The app declares this as a global function. Reassign its lexical binding too, because calls
  // inside the original script can otherwise bypass the window-property override.
  try { scrollToBottom = suppressAutoScroll; } catch (_) {}

  window.addEventListener('load', () => {
    if (typeof window.streamText === 'function') {
      window.streamText = (element, html, callback) => {
        element.innerHTML = String(html || '');
        window.setTimeout(() => callback?.(), 120);
      };
    }
  });

  const demoHaul = [];

  const renderDemoHaul = () => {
    const itemsEl = document.getElementById('cartItems');
    const totalEl = document.getElementById('cartTotal');
    const checkoutEl = document.getElementById('cartCheckoutBtn');
    const badge = document.getElementById('cartBadge');
    if (!itemsEl || !totalEl || !checkoutEl || !badge) return;

    itemsEl.replaceChildren();
    demoHaul.forEach((item) => {
      const row = document.createElement('div');
      row.className = 'cart-item';

      const image = document.createElement('img');
      image.className = 'cart-item-img';
      image.alt = '';
      image.referrerPolicy = 'no-referrer';
      image.src = item.image;

      const info = document.createElement('div');
      info.className = 'cart-item-info';
      const name = document.createElement('div');
      name.className = 'cart-item-name';
      name.textContent = item.name;
      const price = document.createElement('div');
      price.className = 'cart-item-price';
      price.textContent = item.price;
      info.append(name, price);
      row.append(image, info);
      itemsEl.appendChild(row);
    });

    const guestNote = document.createElement('div');
    guestNote.style.cssText = 'border-top:1px solid var(--border);margin-top:12px;padding-top:10px;font-size:0.82rem;color:var(--text-dim)';
    guestNote.textContent = 'Demo guest haul — no account, checkout, or external links are used in this recording.';
    itemsEl.appendChild(guestNote);

    const total = demoHaul.length ? demoHaul[0].price : '$0.00';
    totalEl.textContent = total;
    checkoutEl.disabled = true;
    checkoutEl.textContent = 'Demo recording — checkout disabled';
    badge.textContent = String(demoHaul.length);
    badge.classList.toggle('show', demoHaul.length > 0);
  };

  const lockGuestHaulControls = () => {
    if (!demoHaul.length) return;
    const checkout = document.getElementById('cartCheckoutBtn');
    const disabledLabel = 'Demo recording — checkout disabled';
    if (checkout && (!checkout.disabled || checkout.textContent !== disabledLabel)) {
      checkout.disabled = true;
      checkout.textContent = disabledLabel;
      checkout.setAttribute('aria-disabled', 'true');
    }
    const guestLabel = 'Guest demo haul — sign-in and external checkout are disabled in this recording.';
    const guestNotice = document.querySelector('#cartItems > div:last-child');
    if (guestNotice && guestNotice.textContent !== guestLabel) guestNotice.textContent = guestLabel;
  };

  const cartPanel = document.getElementById('cartPanel');
  if (cartPanel) {
    new MutationObserver(lockGuestHaulControls).observe(cartPanel, {
      childList: true,
      subtree: true,
      characterData: true
    });
  }

  document.addEventListener('click', (event) => {
    const addButton = event.target.closest('.detail-haul-btn');
    if (!addButton) return;
    event.preventDefault();
    event.stopImmediatePropagation();

    const detail = document.getElementById('detailPanel');
    const name = detail?.querySelector('.detail-name')?.textContent?.trim() || 'Selected product';
    const price = detail?.querySelector('.detail-price-main')?.textContent?.trim() || '$0.00';
    const image = document.querySelector('#detailHero img')?.src || '';
    if (!demoHaul.some((item) => item.name === name)) demoHaul.push({ name, price, image });
    renderDemoHaul();
    document.getElementById('detailOverlay')?.classList.remove('show');
    detail?.classList.remove('show');
    window.showToast?.('Added to demo haul');
  }, true);

  window.__recordingDemo = {
    moveCursor,
    pulseCursor,
    hideCursor: () => { cursor.style.opacity = '0'; },
    sequence: 'guest-search-results-detail-haul',
    version: '1.0.0'
  };
})();
