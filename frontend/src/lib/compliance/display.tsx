import styles from "@/pages/AdminPage.module.css";

const META_KEYS = new Set(["success", "error", "message", "correlation_id"]);

export function humanizeLabel(key: string): string {
  return key
    .replaceAll("_", " ")
    .replaceAll(":", " · ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export function formatTimestamp(value?: string | null): string {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

export function unwrapStatistics(raw: unknown): Record<string, unknown> {
  if (!raw || typeof raw !== "object") {
    return {};
  }
  const obj = raw as Record<string, unknown>;
  if (obj.statistics && typeof obj.statistics === "object" && obj.statistics !== null) {
    return obj.statistics as Record<string, unknown>;
  }
  return obj;
}

export interface StatItem {
  label: string;
  value: number | string;
}

export interface BreakdownSection {
  title: string;
  rows: StatItem[];
}

export function parseStatsPayload(raw: unknown): {
  metrics: StatItem[];
  breakdowns: BreakdownSection[];
} {
  const source = unwrapStatistics(raw);
  const metrics: StatItem[] = [];
  const breakdowns: BreakdownSection[] = [];

  for (const [key, value] of Object.entries(source)) {
    if (META_KEYS.has(key)) {
      continue;
    }

    if (typeof value === "number") {
      metrics.push({ label: humanizeLabel(key), value });
      continue;
    }

    if (typeof value === "boolean") {
      metrics.push({ label: humanizeLabel(key), value: value ? "Yes" : "No" });
      continue;
    }

    if (value && typeof value === "object" && !Array.isArray(value)) {
      const rows = Object.entries(value as Record<string, unknown>)
        .filter(([, count]) => typeof count === "number")
        .map(([label, count]) => ({
          label: humanizeLabel(label),
          value: count as number,
        }));

      if (rows.length > 0) {
        breakdowns.push({ title: humanizeLabel(key), rows });
      }
    }
  }

  return { metrics, breakdowns };
}

export function StatGrid({ items }: { items: StatItem[] }) {
  if (items.length === 0) {
    return <p className={styles.loading}>No metrics to show yet.</p>;
  }

  return (
    <div className={styles.grid}>
      {items.map((item) => (
        <div key={item.label} className={styles.card}>
          <p className={styles.cardLabel}>{item.label}</p>
          <p className={styles.cardValue}>{item.value}</p>
        </div>
      ))}
    </div>
  );
}

export function BreakdownTables({ sections }: { sections: BreakdownSection[] }) {
  if (sections.length === 0) {
    return null;
  }

  return (
    <div style={{ display: "grid", gap: "1rem", marginTop: "1rem" }}>
      {sections.map((section) => (
        <div key={section.title}>
          <h3 style={{ margin: "0 0 0.5rem", fontSize: "1rem" }}>{section.title}</h3>
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Item</th>
                  <th>Count</th>
                </tr>
              </thead>
              <tbody>
                {section.rows.map((row) => (
                  <tr key={row.label}>
                    <td>{row.label}</td>
                    <td>{row.value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  );
}

export function CatalogTable({
  title,
  entries,
}: {
  title: string;
  entries: Record<string, string>;
}) {
  const rows = Object.entries(entries);
  if (rows.length === 0) {
    return null;
  }

  return (
    <div style={{ marginTop: "1.5rem" }}>
      <h3 style={{ margin: "0 0 0.75rem" }}>{title}</h3>
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Permission</th>
              <th>Description</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([permission, description]) => (
              <tr key={permission}>
                <td>
                  <span className={styles.role}>{humanizeLabel(permission)}</span>
                </td>
                <td>{description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function EmptyTableRow({ colSpan, message }: { colSpan: number; message: string }) {
  return (
    <tr>
      <td colSpan={colSpan} style={{ color: "#64748b", textAlign: "center" }}>
        {message}
      </td>
    </tr>
  );
}
