setTimeout(async () => {
  const r = await fetch('/api/dashboard/plugins', { headers: { 'X-Hermes-Session-Token': localStorage.getItem('hermes_dashboard_token') || '' } });
  const p = await r.json();
  const out = p.filter(x => x.name.includes('wiki') || x.name.includes('jarvis')).map(x => ({
    name: x.name, entry: x.entry, css: x.css, tab: x.tab
  }));
  return JSON.stringify(out);
}, 2000);
