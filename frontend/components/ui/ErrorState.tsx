type Props = {
  message: string;
  onRetry?: () => void;
};

export default function ErrorState({ message, onRetry }: Props) {
  return (
    <div style={{ textAlign: "center", marginTop: 80 }}>
      <div style={{ fontSize: 14, color: "var(--text-secondary)", marginBottom: 12 }}>{message}</div>
      {onRetry && (
        <button
          onClick={onRetry}
          style={{ fontSize: 12, color: "var(--accent-text)", background: "transparent", border: "1px solid var(--accent)", borderRadius: 6, padding: "8px 20px", cursor: "pointer", opacity: 0.7 }}
        >
          Réessayer
        </button>
      )}
    </div>
  );
}
