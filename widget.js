(function () {
  'use strict';
  var s = document.currentScript;
  if (!s) {
    var all = document.getElementsByTagName('script');
    for (var i = 0; i < all.length; i++) { if (/widget\.js/.test(all[i].src)) { s = all[i]; break; } }
  }
  var attr = function (n, d) {
    var v = s && s.getAttribute('data-' + n);
    return v == null || v === '' ? d : v;
  };
  var API = attr('api', s && s.src ? new URL(s.src).origin : '');
  var TITLE = attr('title', 'KaKoli Ray');
  // which country's circulars the visitor most likely wants: from the browser's time zone / language, nothing is sent anywhere else
  var COUNTRY = (function () {
    var forced = attr('country', '').toUpperCase();
    if (forced === 'BD' || forced === 'IN') return forced;
    try {
      var tz = Intl.DateTimeFormat().resolvedOptions().timeZone || '';
      if (/^Asia\/(Dhaka|Dacca)$/.test(tz)) return 'BD';
      if (/^Asia\/(Kolkata|Calcutta)$/.test(tz)) return 'IN';
      var langs = navigator.languages || [navigator.language || ''];
      for (var i = 0; i < langs.length; i++) {
        if (/-BD$/i.test(langs[i])) return 'BD';
        if (/-IN$/i.test(langs[i])) return 'IN';
      }
    } catch (e) {}
    return '';
  })();
  var SUB = attr('subtitle', 'Assistant, BD JOBS INFO');
  var COLOR = attr('color', '#0E5A45');
  var THEME = attr('theme', 'auto'); // auto | light | dark
  var KEY = 'livechat_hist_v2';
  var REDUCED = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);

  /* ---------- interface text: English by default, then follows the visitor's language ---------- */
  var I18N = {
    en: {
      greet: 'Hi, I\u2019m {name}, the assistant of BD JOBS INFO. Ask me about job circulars, deadlines and how to apply.',
      starters: ['Which circulars were published this week?', 'Which applications close soon?', 'What documents do I need to apply?'],
      open: 'Open chat', close: 'Close chat', fresh: 'New conversation',
      ph: 'Type your question', ask: 'Question', send: 'Send', mic: 'Ask by voice',
      src: 'Sources', retry: 'Try again', up: 'Helpful', down: 'Not helpful', thanks: 'Thanks',
      typing: 'Writing the answer', noans: 'Could not get an answer.',
      net: 'Connection failed. Check your internet and try again.',
      kinds: { post: 'Post', page: 'Page', pdf: 'PDF', image: 'Image', docx: 'Word file', text: 'File' }
    },
    bn: {
      greet: 'হ্যালো, আমি {name}, BD JOBS INFO-এর অ্যাসিস্ট্যান্ট। চাকরির সার্কুলার, শেষ তারিখ বা আবেদনের নিয়ম সম্পর্কে জিজ্ঞাসা করুন।',
      starters: ['এই সপ্তাহের নতুন সার্কুলার কোনগুলো?', 'কোন আবেদনের শেষ তারিখ কাছে?', 'আবেদনে কী কী কাগজ লাগে?'],
      open: 'চ্যাট খুলুন', close: 'চ্যাট বন্ধ করুন', fresh: 'নতুন কথোপকথন',
      ph: 'প্রশ্ন লিখুন', ask: 'প্রশ্ন', send: 'পাঠান', mic: 'কথা বলে প্রশ্ন করুন',
      src: 'সূত্র', retry: 'আবার চেষ্টা করুন', up: 'কাজে লেগেছে', down: 'কাজে লাগেনি', thanks: 'ধন্যবাদ',
      typing: 'উত্তর তৈরি হচ্ছে', noans: 'উত্তর আনা যায়নি।',
      net: 'সংযোগ পাওয়া যায়নি। ইন্টারনেট ঠিক আছে কি না দেখে আবার চেষ্টা করুন।',
      kinds: { post: 'পোস্ট', page: 'পেজ', pdf: 'PDF', image: 'ছবি', docx: 'Word ফাইল', text: 'ফাইল' }
    },
    hi: {
      greet: 'नमस्ते, मैं {name} हूँ, BD JOBS INFO की असिस्टेंट। नौकरी सर्कुलर, अंतिम तिथि या आवेदन के तरीके के बारे में पूछें।',
      starters: [],
      open: 'चैट खोलें', close: 'चैट बंद करें', fresh: 'नई बातचीत',
      ph: 'अपना प्रश्न लिखें', ask: 'प्रश्न', send: 'भेजें', mic: 'बोलकर पूछें',
      src: 'स्रोत', retry: 'फिर कोशिश करें', up: 'उपयोगी', down: 'उपयोगी नहीं', thanks: 'धन्यवाद',
      typing: 'उत्तर तैयार हो रहा है', noans: 'उत्तर नहीं मिल सका।',
      net: 'कनेक्शन नहीं हो सका। इंटरनेट जाँचकर फिर कोशिश करें।',
      kinds: { post: 'पोस्ट', page: 'पेज', pdf: 'PDF', image: 'चित्र', docx: 'Word फ़ाइल', text: 'फ़ाइल' }
    },
    ar: {
      greet: 'مرحبًا، أنا {name}، مساعدة BD JOBS INFO. اسألني عن إعلانات التوظيف والمواعيد النهائية وطريقة التقديم.',
      starters: [],
      open: 'فتح الدردشة', close: 'إغلاق الدردشة', fresh: 'محادثة جديدة',
      ph: 'اكتب سؤالك', ask: 'السؤال', send: 'إرسال', mic: 'اسأل بالصوت',
      src: 'المصادر', retry: 'حاول مرة أخرى', up: 'مفيد', down: 'غير مفيد', thanks: 'شكرًا',
      typing: 'جارٍ كتابة الإجابة', noans: 'تعذر الحصول على إجابة.',
      net: 'فشل الاتصال. تحقق من الإنترنت وحاول مرة أخرى.',
      kinds: { post: 'منشور', page: 'صفحة', pdf: 'PDF', image: 'صورة', docx: 'ملف Word', text: 'ملف' }
    }
  };
  var SPEECH = { bn: 'bn-BD', hi: 'hi-IN', ar: 'ar-SA' };
  var lang = 'en';
  function detect(t) {
    t = t || '';
    if (/[ঀ-৿]/.test(t)) return 'bn';
    if (/[ऀ-ॿ]/.test(t)) return 'hi';
    if (/[؀-ۿ]/.test(t)) return 'ar';
    return 'en';
  }
  function T() { return I18N[lang]; }

  if (attr('font', 'on') !== 'off' && !document.getElementById('livechat-font')) {
    var lk = document.createElement('link');
    lk.id = 'livechat-font'; lk.rel = 'stylesheet';
    lk.href = 'https://fonts.maateen.me/solaiman-lipi/font.css';
    document.head.appendChild(lk);
  }
  var FONT_URL = attr('font-url', '');
  if (FONT_URL) {
    var fs = document.createElement('style');
    fs.textContent = '@font-face{font-family:"LiveChatBn";src:url("' + FONT_URL.replace(/["\\)]/g, '') + '");font-display:swap}';
    document.head.appendChild(fs);
  }

  /* ---------- icons ---------- */
  var P = {
    chat: '<path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/>',
    down: '<polyline points="6 9 12 15 18 9"/>',
    close: '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
    reset: '<polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>',
    mic: '<path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/>',
    send: '<line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/>',
    up: '<path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/>',
    dn: '<path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/>',
    doc: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>',
    img: '<rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/>',
    check: '<polyline points="20 6 9 17 4 12"/>'
  };
  function icon(n, size) {
    size = size || 20;
    return '<svg viewBox="0 0 24 24" width="' + size + '" height="' + size + '" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + P[n] + '</svg>';
  }
  var KIND_ICON = { post: 'doc', page: 'doc', pdf: 'doc', docx: 'doc', text: 'doc', image: 'img' };

  /* ---------- text helpers ---------- */
  function esc(t) {
    return String(t).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; });
  }
  function anchor(url, label) {
    return '<a class="lk" href="' + safeUrl(url) + '" target="_blank" rel="noopener noreferrer">' + label + '</a>';
  }
  function inline(t) {
    var links = [], s = esc(t);
    function keep(html) { links.push(html); return '\u0001' + (links.length - 1) + '\u0001'; }
    // [label](https://...)
    s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, function (_, label, url) { return keep(anchor(url, label)); });
    // plain https://... addresses, without the punctuation that follows them
    s = s.replace(/https?:\/\/[^\s<]+/g, function (u) {
      var m = u.match(/[).,;:!?\u0964'"]+$/), tail = '';
      if (m) { tail = m[0]; u = u.slice(0, -tail.length); }
      return keep(anchor(u, u)) + tail;
    });
    s = s.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/\[(\d+)\]/g, '<sup class="cite">$1</sup>');
    return s.replace(/\u0001(\d+)\u0001/g, function (_, i) { return links[+i]; });
  }
  function fmt(t) {
    var out = '', inList = false;
    String(t).split('\n').forEach(function (l) {
      var m = l.match(/^\s*(?:[-*•]|\d+[.)])\s+(.*)$/);
      if (m) {
        if (!inList) { out += '<ul>'; inList = true; }
        out += '<li>' + inline(m[1]) + '</li>';
      } else {
        if (inList) { out += '</ul>'; inList = false; }
        if (l.trim()) out += '<p>' + inline(l) + '</p>';
      }
    });
    if (inList) out += '</ul>';
    return out;
  }
  function safeUrl(u) { return /^https?:\/\//i.test(u) ? u : '#'; }

  /* ---------- styles ---------- */
  var LIGHT = '--green:' + COLOR + ';--link:' + COLOR + ';--surface:#fff;--bg:#F1F4F3;--ink:#14201C;--muted:#5B6B65;--line:#DCE3E0;--mark:#FFE9A8;--mark-ink:#3B2F00;--danger:#B3261E;--shadow:0 14px 44px rgba(10,30,24,.24),0 2px 8px rgba(10,30,24,.12);';
  var DARK = '--surface:#17211D;--bg:#0F1613;--ink:#E7EFEB;--muted:#97AAA1;--line:#2B3934;--mark:#4D3E08;--mark-ink:#FFE9A8;--danger:#F2B8B5;--link:#7DD3B1;--shadow:0 14px 44px rgba(0,0,0,.55);';
  var CSS =
    ':host{all:initial;' + LIGHT + (THEME === 'dark' ? DARK : '') + '}' +
    (THEME === 'auto' ? '@media (prefers-color-scheme:dark){:host{' + DARK + '}}' : '') +
    '*{box-sizing:border-box;margin:0;padding:0}' +
    'button,input{font:inherit;color:inherit}' +
    'button{cursor:pointer;background:none;border:0}' +
    ':focus-visible{outline:2px solid var(--link);outline-offset:2px}' +
    'a.lk{color:var(--link);text-decoration:underline;word-break:break-all;cursor:pointer}' +
    '.fab,.panel{font-family:"Segoe UI",Roboto,"Helvetica Neue",Arial,"LiveChatBn","SolaimanLipi","Noto Sans Bengali","Nirmala UI",sans-serif;color:var(--ink);-webkit-font-smoothing:antialiased}' +
    '.fab{position:fixed;right:18px;bottom:18px;width:58px;height:58px;border-radius:50%;background:var(--green);color:#fff;display:grid;place-items:center;box-shadow:0 6px 20px rgba(10,30,24,.35);z-index:2147483000;transition:transform .15s}' +
    '.fab:hover{transform:scale(1.05)}.fab svg{grid-area:1/1;transition:opacity .15s,transform .2s}' +
    '.fab .i-down{opacity:0;transform:rotate(-90deg)}.fab[aria-expanded=true] .i-chat{opacity:0;transform:rotate(90deg)}.fab[aria-expanded=true] .i-down{opacity:1;transform:none}' +
    '.panel{position:fixed;right:18px;bottom:88px;width:min(392px,calc(100vw - 28px));height:min(620px,calc(100vh - 108px));height:min(620px,calc(100dvh - 108px));background:var(--surface);border-radius:18px;box-shadow:var(--shadow);display:flex;flex-direction:column;overflow:hidden;z-index:2147483000;border:1px solid var(--line)}' +
    '.panel[hidden]{display:none}' +
    '.panel.in{animation:lcin .18s ease-out}@keyframes lcin{from{opacity:0;transform:translateY(10px) scale(.98)}to{opacity:1;transform:none}}' +
    'header{background:var(--green);color:#fff;display:flex;align-items:center;gap:11px;padding:13px 10px 13px 15px}' +
    '.logo{width:40px;height:40px;border-radius:11px;background:rgba(255,255,255,.16);display:grid;place-items:center;flex:none;overflow:hidden}' +
    '.logo.ph{border-radius:50%;background:none;box-shadow:0 0 0 2px rgba(255,255,255,.55)}.logo img{width:100%;height:100%;object-fit:cover;display:block}' +
    '.hd{flex:1;min-width:0}.t{font-size:16.5px;font-weight:650;line-height:1.25;letter-spacing:.01em}.st{font-size:12.5px;opacity:.82;line-height:1.35;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}' +
    '.ib{width:34px;height:34px;border-radius:10px;display:grid;place-items:center;color:#fff;opacity:.88}.ib:hover{background:rgba(255,255,255,.15);opacity:1}' +
    '.log{position:relative;flex:1;overflow-y:auto;padding:16px 14px;background:var(--bg);display:flex;flex-direction:column;gap:12px;scroll-behavior:smooth}' +
    '.m{max-width:92%;font-size:15px;line-height:1.62;overflow-wrap:anywhere}' +
    '.u{align-self:flex-end;max-width:82%;background:var(--green);color:#fff;padding:9px 13px;border-radius:14px 14px 4px 14px}' +
    '.b{align-self:flex-start;background:var(--surface);border:1px solid var(--line);padding:11px 13px;border-radius:14px 14px 14px 4px}' +
    '.b p{margin:0 0 .55em}.b p:last-child{margin-bottom:0}.b ul{margin:.3em 0 .55em;padding-inline-start:1.15em}.b li{margin:.15em 0}' +
    '.b b{font-weight:650;background:var(--mark);color:var(--mark-ink);padding:0 .22em;border-radius:3px;-webkit-box-decoration-break:clone;box-decoration-break:clone}' +
    '.cite,.sn{display:inline-grid;place-items:center;min-width:17px;height:17px;padding:0 4px;border-radius:9px;font-size:10.5px;font-weight:650;line-height:1;background:#DDEBE5;background:color-mix(in srgb,var(--green) 14%,var(--surface));color:var(--link);vertical-align:2px;margin:0 1px}' +
    '.srcs{margin-top:11px;display:flex;flex-direction:column;gap:6px}' +
    '.sl{font-size:12.5px;color:var(--muted);margin-bottom:1px}' +
    'a.s{display:flex;gap:10px;align-items:center;padding:8px 10px;border:1px solid var(--line);border-radius:10px;text-decoration:none;color:var(--ink);background:var(--surface);transition:background .12s,border-color .12s}' +
    'a.s:hover{background:var(--bg);border-color:var(--green)}' +
    '.sn{vertical-align:baseline;margin:0;flex:none}' +
    '.sx{min-width:0;display:flex;flex-direction:column}' +
    '.sti{font-size:13.5px;line-height:1.4;font-weight:500;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}' +
    '.sk{font-size:12px;color:var(--muted);display:flex;align-items:center;gap:4px;margin-top:1px}' +
    '.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:11px}' +
    '.chip{border:1px solid var(--line);background:var(--surface);color:var(--link);border-radius:999px;padding:6px 12px;font-size:13.5px;line-height:1.35;text-align:start}' +
    '.chip:hover{border-color:var(--green);background:var(--bg)}' +
    '.fb{margin-top:8px;display:flex;align-items:center;gap:2px;color:var(--muted);font-size:12.5px}' +
    '.fb button{width:30px;height:30px;border-radius:8px;display:grid;place-items:center;color:var(--muted)}.fb button:hover{background:var(--bg);color:var(--ink)}' +
    '.fb .ok{display:flex;align-items:center;gap:5px;padding:0 6px;height:30px;color:var(--link)}' +
    '.wl{align-self:stretch;display:flex;flex-direction:column;gap:12px}' +
    '.wl p{font-size:15px;line-height:1.62;color:var(--ink)}' +
    '.sts{display:flex;flex-direction:column;gap:7px}' +
    '.stq{text-align:start;background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:10px 13px;font-size:14.5px;line-height:1.45;color:var(--ink);transition:border-color .12s}' +
    '.stq:hover{border-color:var(--green)}' +
    '.err{border-inline-start:3px solid var(--danger)}' +
    '.retry{margin-top:8px;border:1px solid var(--line);border-radius:8px;padding:5px 11px;font-size:13.5px;color:var(--link);background:var(--surface)}.retry:hover{border-color:var(--green)}' +
    '.dots{display:inline-flex;gap:4px;align-items:center;height:1.6em}.dots i{width:6px;height:6px;border-radius:50%;background:var(--muted);animation:lcb 1s infinite ease-in-out}' +
    '.dots i:nth-child(2){animation-delay:.15s}.dots i:nth-child(3){animation-delay:.3s}@keyframes lcb{0%,60%,100%{opacity:.35;transform:none}30%{opacity:1;transform:translateY(-3px)}}' +
    'form{display:flex;gap:8px;padding:11px 12px 12px;background:var(--surface)}' +
    '.field{flex:1;min-width:0;display:flex;align-items:center;border:1px solid var(--line);border-radius:12px;background:var(--bg);padding-inline-end:4px}' +
    '.field:focus-within{border-color:var(--green);box-shadow:0 0 0 3px rgba(14,90,69,.16)}' +
    'input{flex:1;min-width:0;background:none;border:0;outline:0;padding:11px 6px 11px 13px;font-size:16px}input::placeholder{color:var(--muted)}' +
    'input:focus-visible{outline:0}' +
    '.mic{width:34px;height:34px;border-radius:9px;display:grid;place-items:center;color:var(--muted)}.mic:hover{background:var(--line);color:var(--ink)}' +
    '.mic.on{background:var(--danger);color:#fff;animation:lcp 1.2s infinite}@keyframes lcp{50%{opacity:.65}}' +
    '.send{width:44px;height:44px;flex:none;border-radius:12px;background:var(--green);color:#fff;display:grid;place-items:center;transition:opacity .12s}.send:disabled{opacity:.4;cursor:default}' +
    '.ft{font-size:12px;color:var(--muted);text-align:center;padding:0 12px 11px;background:var(--surface)}' +
    '@media (max-width:480px){.panel{right:8px;left:8px;width:auto;bottom:80px;height:min(640px,calc(100vh - 96px));height:min(640px,calc(100dvh - 96px))}.fab{right:12px;bottom:12px}}' +
    '@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important;scroll-behavior:auto!important}}';

  var host = document.createElement('div');
  document.body.appendChild(host);
  var root = host.attachShadow({ mode: 'open' });
  root.innerHTML =
    '<style>' + CSS + '</style>' +
    '<button class="fab" aria-expanded="false">' + icon('chat', 26).replace('<svg', '<svg class="i-chat"') + icon('down', 26).replace('<svg', '<svg class="i-down"') + '</button>' +
    '<section class="panel" hidden role="dialog">' +
    '<header><div class="logo">' + icon('chat', 21) + '</div><div class="hd"><div class="t"></div><div class="st"></div></div>' +
    '<button class="ib new">' + icon('reset', 18) + '</button>' +
    '<button class="ib x">' + icon('close', 20) + '</button></header>' +
    '<div class="log" role="log" aria-live="polite"></div>' +
    '<form><div class="field"><input type="text" dir="auto" maxlength="500" autocomplete="off">' +
    '<button type="button" class="mic">' + icon('mic', 19) + '</button></div>' +
    '<button type="submit" class="send" disabled>' + icon('send', 20) + '</button></form>' +
    '<p class="ft"></p></section>';

  var $ = function (sel) { return root.querySelector(sel); };
  var fab = $('.fab'), panel = $('.panel'), log = $('.log'), form = $('form'),
      input = $('input'), mic = $('.mic'), sendBtn = $('.send');
  $('.t').textContent = TITLE;

  // profile photo: data-photo="URL", otherwise avatar.jpg/png/webp uploaded next to the server files
  var logo = $('.logo'), photo = new Image();
  photo.alt = '';
  photo.onload = function () { logo.innerHTML = ''; logo.classList.add('ph'); logo.appendChild(photo); };
  photo.src = attr('photo', API + '/avatar');

  function setLabel(el, text) { el.setAttribute('aria-label', text); el.title = text; }
  function applyLang() {
    var t = T();
    $('.st').textContent = SUB;
    input.placeholder = t.ph; input.setAttribute('aria-label', t.ask);
    var ft = $('.ft'); ft.textContent = attr('footer', ''); ft.style.display = ft.textContent ? '' : 'none';
    setLabel(fab, panel.hidden ? t.open : t.close);
    setLabel($('.new'), t.fresh); setLabel($('.x'), t.close);
    setLabel(mic, t.mic); setLabel(sendBtn, t.send);
    panel.setAttribute('aria-label', TITLE);
  }

  var msgs = [];
  try { msgs = JSON.parse(sessionStorage.getItem(KEY) || '[]'); } catch (e) { msgs = []; }
  var busy = false;
  function save() { try { sessionStorage.setItem(KEY, JSON.stringify(msgs.slice(-30))); } catch (e) {} }
  function toEnd() { log.scrollTop = log.scrollHeight; }
  function toTop(el) { log.scrollTop = Math.max(0, el.offsetTop - 10); }
  function lastUserLang() {
    for (var i = msgs.length - 1; i >= 0; i--) if (msgs[i].role === 'user') return detect(msgs[i].content);
    return 'en';
  }

  /* ---------- rendering ---------- */
  function addUser(text) {
    var d = document.createElement('div'); d.className = 'm u'; d.setAttribute('dir', 'auto'); d.textContent = text;
    log.appendChild(d); toEnd();
  }
  function typingBubble() {
    var d = document.createElement('div'); d.className = 'm b';
    d.innerHTML = '<span class="dots" role="status" aria-label="' + esc(T().typing) + '"><i></i><i></i><i></i></span>';
    log.appendChild(d); toEnd(); return d;
  }
  function addBot(m, showChips) {
    var t = I18N[detect(m.content)], d = document.createElement('div');
    d.className = 'm b' + (m.error ? ' err' : ''); d.setAttribute('dir', 'auto');
    var html = fmt(m.content);
    if (m.sources && m.sources.length) {
      html += '<div class="srcs"><div class="sl">' + esc(t.src) + '</div>' + m.sources.map(function (x) {
        var k = x.kind || 'post';
        return '<a class="s" href="' + esc(safeUrl(x.url)) + '" target="_blank" rel="noopener noreferrer">' +
          '<span class="sn">' + esc(x.n) + '</span><span class="sx"><span class="sti">' + esc(x.title) + '</span>' +
          '<span class="sk">' + icon(KIND_ICON[k] || 'doc', 13) + esc(t.kinds[k] || t.kinds.post) + '</span></span></a>';
      }).join('') + '</div>';
    }
    d.innerHTML = html;
    if (m.retryQ) {
      var r = document.createElement('button'); r.className = 'retry'; r.textContent = t.retry;
      r.onclick = function () { render(); send(m.retryQ); };
      d.appendChild(r);
    }
    if (showChips && m.followups && m.followups.length) {
      var c = document.createElement('div'); c.className = 'chips';
      m.followups.forEach(function (f) {
        var b = document.createElement('button'); b.className = 'chip'; b.textContent = f;
        b.onclick = function () { send(f); };
        c.appendChild(b);
      });
      d.appendChild(c);
    }
    if (m.found && m.q) {
      var fb = document.createElement('div'); fb.className = 'fb';
      fb.innerHTML = '<button data-r="1" aria-label="' + esc(t.up) + '" title="' + esc(t.up) + '">' + icon('up', 16) + '</button>' +
        '<button data-r="-1" aria-label="' + esc(t.down) + '" title="' + esc(t.down) + '">' + icon('dn', 16) + '</button>';
      fb.onclick = function (e) {
        var b = e.target.closest && e.target.closest('button'); if (!b) return;
        fetch(API + '/feedback', { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question: m.q, answer: m.content, rating: parseInt(b.getAttribute('data-r'), 10) }) }).catch(function () {});
        fb.innerHTML = '<span class="ok">' + icon('check', 15) + esc(t.thanks) + '</span>';
      };
      d.appendChild(fb);
    }
    log.appendChild(d);
    if (m.error) toEnd(); else toTop(d);
    return d;
  }
  function welcome() {
    var t = T(), w = document.createElement('div'); w.className = 'wl';
    var greet = (lang === 'en' ? attr('greeting', t.greet) : t.greet).replace('{name}', TITLE);
    var custom = attr('starters', '');
    var starters = lang === 'en' && custom ? custom.split('|').filter(Boolean).slice(0, 4) : t.starters;
    w.innerHTML = '<p>' + esc(greet) + '</p>';
    if (starters.length) {
      var l = document.createElement('div'); l.className = 'sts';
      starters.forEach(function (q) {
        var b = document.createElement('button'); b.className = 'stq'; b.textContent = q;
        b.onclick = function () { send(q); };
        l.appendChild(b);
      });
      w.appendChild(l);
    }
    log.appendChild(w);
  }
  var greeted = false, greetTok = 0;
  function render() {
    lang = lastUserLang(); applyLang();
    log.innerHTML = '';
    if (!msgs.length) {
      if (greeted) { welcome(); return; }
      greeted = true;  // first time: the assistant "joins" after a short typing pause
      var tb = typingBubble(), tok = ++greetTok;
      setTimeout(function () {
        if (tok !== greetTok || msgs.length) return;
        tb.remove(); welcome(); toEnd();
      }, 2500);
      return;
    }
    greetTok++;
    msgs.forEach(function (m, i) {
      if (m.role === 'user') addUser(m.content); else addBot(m, i === msgs.length - 1);
    });
  }
  function history() {
    return msgs.slice(-6).map(function (m) { return { role: m.role, content: String(m.content || '').slice(0, 1200) }; });
  }

  /* ---------- sending ---------- */
  function fail(text, q, retryable) {
    msgs.pop(); save();
    addBot({ role: 'assistant', content: text, error: true, retryQ: retryable ? q : null }, false);
  }
  function send(q) {
    q = (q || '').trim();
    if (!q || busy) return;
    busy = true;
    var hist = history();
    lang = detect(q); applyLang();
    if (!msgs.length) log.innerHTML = '';
    Array.prototype.forEach.call(log.querySelectorAll('.chips'), function (c) { c.remove(); });
    msgs.push({ role: 'user', content: q }); addUser(q);
    input.value = ''; sendBtn.disabled = true;
    var typing = typingBubble();
    fetch(API + '/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: q, history: hist, country: COUNTRY }) })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, status: r.status, j: j }; }); })
      .then(function (res) {
        typing.remove();
        if (res.ok) {
          var m = { role: 'assistant', content: res.j.answer, sources: res.j.sources, followups: res.j.followups, found: res.j.found, q: q };
          msgs.push(m); addBot(m, true); save();
        } else {
          fail((res.j && typeof res.j.detail === 'string' && res.j.detail) || T().noans, q, res.status >= 500 || res.status === 422);
        }
      })
      .catch(function () {
        typing.remove();
        fail(T().net, q, true);
      })
      .then(function () { busy = false; });
  }

  /* ---------- open / close ---------- */
  function open() {
    panel.hidden = false; fab.setAttribute('aria-expanded', 'true');
    if (!REDUCED) { panel.classList.remove('in'); void panel.offsetWidth; panel.classList.add('in'); }
    render(); toEnd();
    if (!/Mobi|Android/i.test(navigator.userAgent)) input.focus();
  }
  function close() {
    panel.hidden = true; fab.setAttribute('aria-expanded', 'false'); applyLang(); fab.focus();
  }
  fab.onclick = function () { if (panel.hidden) open(); else close(); };
  $('.x').onclick = close;
  $('.new').onclick = function () { msgs = []; save(); render(); input.focus(); };
  panel.addEventListener('keydown', function (e) { if (e.key === 'Escape') close(); });
  form.onsubmit = function (e) { e.preventDefault(); send(input.value); };
  input.addEventListener('input', function () { sendBtn.disabled = !input.value.trim(); });
  applyLang();

  /* ---------- voice: language follows the conversation automatically ---------- */
  var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) { mic.style.display = 'none'; }
  else {
    var rec = null;
    mic.onclick = function () {
      if (rec) { rec.stop(); return; }
      rec = new SR();
      rec.lang = SPEECH[lang] || navigator.language || 'en-US';
      rec.interimResults = false;
      rec.onresult = function (e) { input.value = e.results[0][0].transcript; send(input.value); };
      rec.onend = function () { mic.classList.remove('on'); rec = null; };
      rec.onerror = function () { mic.classList.remove('on'); rec = null; };
      mic.classList.add('on'); rec.start();
    };
  }
})();
