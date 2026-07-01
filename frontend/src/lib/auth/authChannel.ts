const AUTH_CHANNEL = "auth";

export function broadcastLogout() {
  if (typeof BroadcastChannel === "undefined") return;
  const channel = new BroadcastChannel(AUTH_CHANNEL);
  channel.postMessage({ type: "LOGOUT" });
  channel.close();
}

export function subscribeLogout(listener: () => void) {
  if (typeof BroadcastChannel === "undefined") return () => undefined;
  const channel = new BroadcastChannel(AUTH_CHANNEL);
  channel.onmessage = (event) => {
    if (event.data?.type === "LOGOUT") {
      listener();
    }
  };
  return () => channel.close();
}
