import styles from "./AuthBootstrapShell.module.css";

export function AuthBootstrapShell() {
  return (
    <div className={styles.shell}>
      <div className={styles.card}>
        <div className={styles.spinner} aria-hidden />
        <p>Loading your session…</p>
      </div>
    </div>
  );
}
