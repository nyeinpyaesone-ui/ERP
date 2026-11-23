/**
 * Open an authenticated ERP WebSocket without placing bearer tokens in URLs.
 * The backend requires the first client frame to be { type: "authenticate", token }.
 */
export function connectAuthenticatedWebSocket(url, token = localStorage.getItem('token')) {
  const socket = new WebSocket(url);

  socket.addEventListener('open', () => {
    if (!token) {
      socket.close(4401, 'Authentication required');
      return;
    }
    socket.send(JSON.stringify({ type: 'authenticate', token }));
  }, { once: true });

  return socket;
}
