interface StageIndicatorProps {
  number: number
  label: string
  status: "pending" | "running" | "done"
}

export function StageIndicator({ number, label, status }: StageIndicatorProps) {
  return (
    <div className="flex items-center gap-3 py-1.5">
      <div
        className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-[10px] font-medium ${
          status === "done"
            ? "border-foreground bg-foreground text-primary-foreground"
            : status === "running"
            ? "border-foreground bg-foreground text-primary-foreground animate-pulse"
            : "border-border bg-background text-muted-foreground"
        }`}
      >
        {number}
      </div>
      <span
        className={`text-sm ${
          status === "pending" ? "text-muted-foreground" : "text-foreground"
        }`}
      >
        {label}
      </span>
    </div>
  )
}

export default StageIndicator
