/**
 * ═══════════════════════════════════════════════════════════════════
 * GISL SCHOOLS — APPLICATION LOGGER
 * Drop-in debug logger — loads before all other scripts.
 * Provides appLogger.info/warn/error/debug() globally.
 * ═══════════════════════════════════════════════════════════════════
 */

const _LOGGER_CFG = {
  level: 'info',       // 'debug' | 'info' | 'warn' | 'error'
  enableConsole: true,
  enableStorage: true,
  maxLogs: 500
};

class AppLogger {
  constructor(cfg) {
    this.cfg = { ..._LOGGER_CFG, ...cfg };
    this.logs = [];
    this._loadFromStorage();
  }

  _loadFromStorage() {
    try {
      const saved = localStorage.getItem('gisl_app_logs');
      if (saved) this.logs = JSON.parse(saved);
    } catch (e) { /* ignore */ }
  }

  _save() {
    try {
      if (this.logs.length > this.cfg.maxLogs) this.logs.shift();
      localStorage.setItem('gisl_app_logs', JSON.stringify(this.logs));
    } catch (e) { /* ignore */ }
  }

  log(level, module, message, data) {
    const entry = {
      id: Date.now() + Math.random(),
      timestamp: new Date().toISOString(),
      level, module, message, data,
      user: localStorage.getItem('userEmail') || 'anon'
    };
    this.logs.push(entry);
    this._save();

    if (this.cfg.enableConsole) {
      const colours = { debug: '#6b7280', info: '#3b82f6', warn: '#f59e0b', error: '#ef4444' };
      const style = `color:${colours[level] || '#3b82f6'};font-weight:600`;
      const time = new Date(entry.timestamp).toLocaleTimeString();
      console.log(`%c[${time}] ${level.toUpperCase()} — ${module}: ${message}`, style);
      if (data) console.log(data);
    }
    return entry;
  }

  debug(module, msg, data) { return this.log('debug', module, msg, data); }
  info(module, msg, data)  { return this.log('info',  module, msg, data); }
  warn(module, msg, data)  { return this.log('warn',  module, msg, data); }
  error(module, msg, data) { return this.log('error', module, msg, data); }

  getLogs(filter = {}) {
    return this.logs.filter(l =>
      (!filter.level  || l.level  === filter.level) &&
      (!filter.module || l.module === filter.module)
    );
  }

  clearLogs() {
    this.logs = [];
    localStorage.removeItem('gisl_app_logs');
  }

  exportJSON() { return JSON.stringify(this.logs, null, 2); }
}

// Global singleton — available as appLogger everywhere
const appLogger = new AppLogger();

// Catch global JS errors
window.addEventListener('error', (ev) => {
  appLogger.error('Global', ev.message, {
    file: ev.filename, line: ev.lineno, col: ev.colno,
    stack: ev.error?.stack
  });
});
window.addEventListener('unhandledrejection', (ev) => {
  appLogger.error('Promise', ev.reason?.message || String(ev.reason), { reason: ev.reason });
});
