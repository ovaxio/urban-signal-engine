type Props = {
  message: string;
  onRetry?: () => void;
};

export default function ErrorState({ message, onRetry }: Props) {
  return (
    <div style={{ textAlign: "center", marginTop: 80 }}>
      <div style={{ fontSize: 14, color: "#94a3b8", marginBottom: 12 }}>{message}</div>
      {onRetry && (
        <button
          onClick={onRetry}
          style={{ fontSize: 12, color: "#a5b4fc", background: "transparent", border: "1px solid #6366f144", borderRadius: 6, padding: "8px 20px", cursor: "pointer" }}
        >
          Réessayer
        </button>
      )}
    </div>
  );
}
