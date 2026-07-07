import { type FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getApiError } from "@/lib/apiClient";
import {
  disable2fa,
  enable2fa,
  fetch2faStatus,
  fetchPasswordHistory,
  verify2fa,
} from "@/lib/security/api";
import styles from "@/pages/ProfilePage.module.css";

export function TwoFactorPanel() {
  const queryClient = useQueryClient();
  const [totpCode, setTotpCode] = useState("");
  const [disableCode, setDisableCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [setup, setSetup] = useState<{
    qr_code: string;
    backup_codes: string[];
  } | null>(null);

  const statusQuery = useQuery({
    queryKey: ["2fa", "status"],
    queryFn: fetch2faStatus,
  });

  const enableMutation = useMutation({
    mutationFn: enable2fa,
    onSuccess: (data) => {
      setSetup({ qr_code: data.qr_code, backup_codes: data.backup_codes });
      setMessage(data.message);
      setError(null);
    },
    onError: (err) => setError(getApiError(err).detail),
  });

  const verifyMutation = useMutation({
    mutationFn: () => verify2fa(totpCode),
    onSuccess: (data) => {
      if (!data.success) {
        setError(data.message);
        return;
      }
      setMessage(data.message);
      setError(null);
      setSetup(null);
      setTotpCode("");
      void queryClient.invalidateQueries({ queryKey: ["2fa", "status"] });
    },
    onError: (err) => setError(getApiError(err).detail),
  });

  const disableMutation = useMutation({
    mutationFn: () => disable2fa(disableCode),
    onSuccess: (data) => {
      setMessage(data.message);
      setError(null);
      setDisableCode("");
      void queryClient.invalidateQueries({ queryKey: ["2fa", "status"] });
    },
    onError: (err) => setError(getApiError(err).detail),
  });

  const historyQuery = useQuery({
    queryKey: ["password", "history"],
    queryFn: fetchPasswordHistory,
  });

  if (statusQuery.isLoading) {
    return <p className={styles.loading}>Loading security settings…</p>;
  }

  const enabled = statusQuery.data?.is_enabled;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      <div className={styles.card}>
        <h2>Two-factor authentication</h2>
        <p className={styles.subtitle}>
          Status: {enabled ? "Enabled" : setup ? "Pending verification" : "Disabled"}
        </p>

        {error && <p className={styles.error}>{error}</p>}
        {message && <p className={styles.success}>{message}</p>}

        {!enabled && !setup && (
          <button
            type="button"
            className={styles.primaryBtn}
            disabled={enableMutation.isPending}
            onClick={() => enableMutation.mutate()}
          >
            {enableMutation.isPending ? "Starting…" : "Enable 2FA"}
          </button>
        )}

        {setup && (
          <div className={styles.form}>
            <img src={setup.qr_code} alt="2FA QR code" style={{ maxWidth: 220 }} />
            <p className={styles.subtitle}>Backup codes (save these):</p>
            <code>{setup.backup_codes.join(", ")}</code>
            <label>
              Verification code
              <input
                value={totpCode}
                onChange={(e) => setTotpCode(e.target.value)}
                maxLength={6}
                inputMode="numeric"
                required
              />
            </label>
            <button
              type="button"
              className={styles.primaryBtn}
              disabled={verifyMutation.isPending || totpCode.length !== 6}
              onClick={() => verifyMutation.mutate()}
            >
              {verifyMutation.isPending ? "Verifying…" : "Verify and enable"}
            </button>
          </div>
        )}

        {enabled && (
          <form
            className={styles.form}
            onSubmit={(e: FormEvent) => {
              e.preventDefault();
              disableMutation.mutate();
            }}
          >
            <label>
              Current 2FA code to disable
              <input
                value={disableCode}
                onChange={(e) => setDisableCode(e.target.value)}
                maxLength={6}
                inputMode="numeric"
                required
              />
            </label>
            <button
              type="submit"
              className={styles.dangerBtn}
              disabled={disableMutation.isPending}
            >
              {disableMutation.isPending ? "Disabling…" : "Disable 2FA"}
            </button>
          </form>
        )}
      </div>

      <div className={styles.card}>
        <h2>Password history</h2>
        {historyQuery.isLoading && <p className={styles.loading}>Loading…</p>}
        {historyQuery.error && (
          <p className={styles.error}>{getApiError(historyQuery.error).detail}</p>
        )}
        {historyQuery.data ? (
          <pre style={{ fontSize: "0.8rem", overflow: "auto" }}>
            {JSON.stringify(historyQuery.data, null, 2)}
          </pre>
        ) : null}
      </div>
    </div>
  );
}
