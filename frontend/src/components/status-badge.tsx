import { Loader2Icon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { RunStatus } from "@/lib/api";
import { STATUS_LABEL } from "@/lib/format";

const VARIANT: Record<RunStatus, "secondary" | "outline" | "destructive"> = {
  running: "outline",
  completed: "secondary",
  failed: "destructive",
  step_limit: "destructive",
  error: "destructive",
};

export function StatusBadge({ status, label }: { status: RunStatus; label?: string }) {
  return (
    <Badge variant={VARIANT[status]} className="gap-1">
      {status === "running" && <Loader2Icon className="size-3 animate-spin" />}
      {label ?? STATUS_LABEL[status]}
    </Badge>
  );
}
