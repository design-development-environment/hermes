function validate(input) {
  const raw=String(input || '').trim();
  const url=new URL(raw.includes('://') ? raw : 'https://'+raw);
  const local=url.origin==='http://127.0.0.1:3000';
  const name=url.hostname;
  const privateHost=/^(?:[a-z0-9-]+\.)+ts\.net$/i.test(name) ||
    /^100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d+\.\d+$/.test(name) || name.startsWith('[fd7a:115c:a1e0:');
  if (!(local || (url.protocol==='https:' && privateHost)) || url.username || url.password || url.pathname!=='/' || url.search || url.hash)
    throw Error('Enter your host’s private Tailscale address or choose This computer.');
  return url.origin;
}
module.exports={validate};
