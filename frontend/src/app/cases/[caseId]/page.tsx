import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { Workspace } from "@/components/workspace/workspace";

// Reading route params is request-time data, so it sits inside <Suspense> and the
// rest of the page can be prerendered (Next.js cache components).
async function CaseWorkspace({ params }: { params: PageProps<"/cases/[caseId]">["params"] }) {
  const { caseId } = await params;
  return <Workspace caseId={caseId} />;
}

export default function CasePage({ params }: PageProps<"/cases/[caseId]">) {
  return (
    <Suspense fallback={<Skeleton className="h-[70vh] w-full" />}>
      <CaseWorkspace params={params} />
    </Suspense>
  );
}
