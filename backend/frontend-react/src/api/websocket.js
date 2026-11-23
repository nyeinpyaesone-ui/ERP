/**
 * Open an authenticated ERP WebSocket without placing bearer tokens in URLs.
 * The backend requires the first client frame to be { type: "authenticate", token }.
 */
export function connectAuthenticatedWebSocket(url, token = localStorage.getItem('token')) {
  const target = new URL(url, window.location.href);
  if (!['ws:', 'wss:'].includes(target.protocol)) {
    throw new Error('WebSocket URL must use ws:// or wss://');
  }
  if (window.location.protocol === 'https:' && target.protocol !== 'wss:') {
    throw new Error('Secure pages require wss:// WebSocket connections');
  }

  const socket = new WebSocket(target.toString());

  socket.addEventListener('open', () => {
    if (!token) {
      socket.close(4401, 'Authentication required');
      return;
    }
    socket.send(JSON.stringify({ type: 'authenticate', token }));
  }, { once: true });

  return socket;
}
