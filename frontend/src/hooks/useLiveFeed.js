import { useEffect, useState } from "react";

export function useLiveFeed() {
  const [events, setEvents] = useState([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) return;
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${window.location.host}/api/v1/ws/live?token=${token}`);
    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        setEvents((prev) => [msg, ...prev].slice(0, 50));
      } catch {}
    };
    return () => ws.close();
  }, []);

  return { events, connected };
}
