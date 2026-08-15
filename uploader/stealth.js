/**
 * stealth_lite.js – Bản tối giản cho CloakBrowser
 * CHỈ dọn dẹp dấu vết Playwright/CDP, KHÔNG override fingerprint
 * (vì CloakBrowser đã xử lý fingerprint ở cấp C++ rồi)
 */
(() => {
  'use strict';

  // 1. Dọn dẹp Playwright CDP artifacts hoàn toàn không để lại dấu vết
  const cleanPlaywright = () => {
    try {
      if (window.__playwright) delete window.__playwright;
      if (window.__pw_manual) delete window.__pw_manual;
      if (window.__PW_inspect) delete window.__PW_inspect;
      
      const cdcKeys = Object.keys(document).filter(k => /^cdc_/.test(k));
      cdcKeys.forEach(k => { try { delete document[k]; } catch(e) {} });
      
      const windowCdc = Object.keys(window).filter(k => /^\$cdc_|^cdc_/.test(k));
      windowCdc.forEach(k => { try { delete window[k]; } catch(e) {} });
    } catch(e) {}
  };

  cleanPlaywright();
  setInterval(cleanPlaywright, 100);

  // 2. Ẩn navigator.webdriver nếu chưa bị ẩn
  try {
    if (navigator.webdriver) {
      delete Navigator.prototype.webdriver;
    }
  } catch (e) {}

  // 3. Đảm bảo chrome.runtime tồn tại (không override nếu đã có)
  if (!window.chrome) window.chrome = {};
  if (!window.chrome.runtime) {
    window.chrome.runtime = {
      connect: function() { return { onDisconnect: { addListener: function(){} } }; },
      sendMessage: function() {},
      id: undefined
    };
  }
})();
