/**
 * alongkit.webdev.probes.js - In-page geometry probes, overflow detection, and API spies.
 */
(function() {
  window.__along_probes__ = window.__along_probes__ || {};
  window.__along_spies__ = window.__along_spies__ || {};

  function resolveElement(target) {
    if (!target) return null;
    if (target instanceof Element) return target;
    if (typeof target === 'string') return document.querySelector(target);
    if (typeof target === 'object') {
      if (target.role) {
        var els = Array.from(document.querySelectorAll('[role="' + target.role + '"], ' + target.role));
        if (target.name) {
          els = els.filter(function(e) {
            return (e.innerText || e.getAttribute('aria-label') || '').trim() === target.name;
          });
        }
        return els[0] || null;
      }
      if (target.test_id) return document.querySelector('[data-testid="' + target.test_id + '"]');
      if (target.css) return document.querySelector(target.css);
    }
    return null;
  }

  window.__along_probes__.box = function(target) {
    var el = resolveElement(target);
    if (!el) return null;
    var rect = el.getBoundingClientRect();
    return {
      x: rect.x,
      y: rect.y,
      width: rect.width,
      height: rect.height,
      top: rect.top,
      right: rect.right,
      bottom: rect.bottom,
      left: rect.left
    };
  };

  window.__along_probes__.above = function(targetA, targetB) {
    var boxA = window.__along_probes__.box(targetA);
    var boxB = window.__along_probes__.box(targetB);
    if (!boxA || !boxB) return false;
    return boxA.bottom <= boxB.top;
  };

  window.__along_probes__.covered_by = function(target) {
    var el = resolveElement(target);
    if (!el) return { self: false, reason: 'element_not_found' };
    var rect = el.getBoundingClientRect();
    var cx = rect.left + rect.width / 2;
    var cy = rect.top + rect.height / 2;
    var topmost = document.elementFromPoint(cx, cy);
    var isSelf = (topmost === el) || (el.contains(topmost));
    return {
      self: isSelf,
      topmost_tag: topmost ? topmost.tagName.toLowerCase() : null,
      topmost_id: topmost ? topmost.id : null,
      topmost_class: topmost ? topmost.className : null,
      topmost_role: topmost ? topmost.getAttribute('role') : null
    };
  };

  window.__along_probes__.overflow_x = function() {
    var docWidth = document.documentElement.clientWidth || window.innerWidth;
    var scrollWidth = document.documentElement.scrollWidth;
    var isOverflow = scrollWidth > (docWidth + 1);
    var offending = [];
    if (isOverflow) {
      var all = Array.from(document.body.querySelectorAll('*'));
      all.forEach(function(e) {
        var r = e.getBoundingClientRect();
        if (r.right > docWidth + 2) {
          offending.push({
            tag: e.tagName.toLowerCase(),
            id: e.id || '',
            className: typeof e.className === 'string' ? e.className : '',
            right: r.right,
            excess: r.right - docWidth
          });
        }
      });
    }
    return {
      overflow: isOverflow,
      client_width: docWidth,
      scroll_width: scrollWidth,
      offending_elements: offending.slice(0, 10)
    };
  };

  window.__along_probes__.in_viewport = function(target) {
    var box = window.__along_probes__.box(target);
    if (!box) return false;
    var vw = window.innerWidth;
    var vh = window.innerHeight;
    return box.top >= 0 && box.left >= 0 && box.bottom <= vh && box.right <= vw;
  };

  window.__along_probes__.install_spy = function(targetPath) {
    window.__along_spies__[targetPath] = [];
    var parts = targetPath.split('.');
    var obj = window;
    for (var i = 0; i < parts.length - 1; i++) {
      if (!obj[parts[i]]) obj[parts[i]] = {};
      obj = obj[parts[i]];
    }
    var fnName = parts[parts.length - 1];
    var origFn = obj[fnName];

    obj[fnName] = function() {
      var args = Array.from(arguments);
      window.__along_spies__[targetPath].push({
        args: args,
        timestamp: Date.now()
      });
      if (typeof origFn === 'function') {
        return origFn.apply(this, arguments);
      }
    };
  };

  window.__along_probes__.get_spy_calls = function(targetPath) {
    return window.__along_spies__[targetPath] || [];
  };
})();
