"use client";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="mx-auto mt-10 max-w-2xl rounded-2xl border border-rose-300 bg-rose-50 p-6">
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-rose-700">UI Error</p>
      <h1 className="mt-2 text-2xl font-semibold text-rose-900">Something broke in the dashboard.</h1>
      <p className="mt-2 text-sm text-rose-800">{error.message || "Unknown frontend error."}</p>
      <button
        type="button"
        onClick={reset}
        className="mt-4 rounded-lg bg-rose-700 px-4 py-2 text-sm font-medium text-white"
      >
        Try again
      </button>
    </main>
  );
}
