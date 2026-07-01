import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <main style={{ padding: "2rem", maxWidth: 480 }}>
      <h1>404 — Page not found</h1>
      <p>
        <Link to="/">Return home</Link>
      </p>
    </main>
  );
}
