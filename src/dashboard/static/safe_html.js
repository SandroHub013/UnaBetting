(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.SafeHtml = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  function escape(value) {
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function tableCell(value, allowHtml = false) {
    if (value === null || value === undefined) return '—';
    return allowHtml ? String(value) : escape(value);
  }

  return Object.freeze({ escape, tableCell });
});
