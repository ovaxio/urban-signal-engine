type Props = {
  message: string;
  onRetry?: () => void;
};

export default function ErrorState({ message, onRetry }: Props) {
  return (
    <div className="mt-20 text-center">
      <div className="mb-3 text-sm text-text-secondary">{message}</div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="cursor-pointer rounded-md border border-accent bg-transparent px-5 py-2 text-xs text-accent-text opacity-70"
        >
          Réessayer
        </button>
      )}
    </div>
  );
}
