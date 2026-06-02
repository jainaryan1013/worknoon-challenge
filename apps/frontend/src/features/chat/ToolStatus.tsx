export function ToolStatus({ summary }: { summary: string }) {
  return (
    <div className="flex items-center gap-2 text-xs text-gray-500" role="status">
      <span className="h-2 w-2 animate-pulse rounded-full bg-blue-400" />
      {summary}
    </div>
  );
}
