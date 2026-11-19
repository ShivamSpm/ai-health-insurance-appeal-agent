"use client";

import { diffWords } from "diff";
import { CopyIcon, DownloadIcon, SaveIcon } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { api, type DraftVersion } from "@/lib/api";
import { when } from "@/lib/format";
import { Markdown } from "./markdown";

function versionLabel(d: DraftVersion): string {
  return d.version === 0 ? "Agent draft" : `Your edit ${d.version} · ${when(d.created_at)}`;
}

function Changes({ from, to }: { from: string; to: string }) {
  const parts = useMemo(() => diffWords(from, to), [from, to]);
  if (from === to) {
    return <p className="text-sm text-muted-foreground">{"No changes from the agent's draft."}</p>;
  }
  return (
    <div className="text-sm leading-6 whitespace-pre-wrap">
      {parts.map((p, i) =>
        p.added ? (
          <ins key={i} className="bg-emerald-100 text-emerald-900 no-underline">
            {p.value}
          </ins>
        ) : p.removed ? (
          <del key={i} className="bg-red-100 text-red-900">
            {p.value}
          </del>
        ) : (
          <span key={i}>{p.value}</span>
        ),
      )}
    </div>
  );
}

export function DraftPanel({
  runId,
  caseId,
  onCite,
  onCitedChange,
}: {
  runId: string;
  caseId: string;
  onCite: (chunkId: string) => void;
  onCitedChange: (text: string) => void;
}) {
  const [versions, setVersions] = useState<DraftVersion[] | null>(null);
  const [version, setVersion] = useState(0);
  const [text, setText] = useState("");
  const [tab, setTab] = useState("preview");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api.drafts(runId).then(
      (list) => {
        if (cancelled) return;
        const latest = list[list.length - 1];
        setVersions(list);
        setVersion(latest?.version ?? 0);
        setText(latest?.text ?? "");
      },
      (e: Error) => toast.error(e.message),
    );
    return () => {
      cancelled = true;
    };
  }, [runId]);

  useEffect(() => onCitedChange(text), [text, onCitedChange]);

  const current = versions?.find((v) => v.version === version);
  const agent = versions?.find((v) => v.version === 0);
  const dirty = current !== undefined && text !== current.text;

  if (!versions) return <p className="text-sm text-muted-foreground">Loading the draft...</p>;

  async function save() {
    setSaving(true);
    try {
      const saved = await api.saveDraft(runId, text);
      setVersions((vs) => [...(vs ?? []), saved]);
      setVersion(saved.version);
      toast.success(`Saved as edit ${saved.version}.`);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  function download() {
    const url = URL.createObjectURL(new Blob([text], { type: "text/markdown" }));
    const a = Object.assign(document.createElement("a"), {
      href: url,
      download: `appeal-${caseId}-v${version}${dirty ? "-unsaved" : ""}.md`,
    });
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <Tabs value={tab} onValueChange={(v) => setTab(String(v))} className="gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <TabsList>
          <TabsTrigger value="preview">Preview</TabsTrigger>
          <TabsTrigger value="edit">Edit</TabsTrigger>
          <TabsTrigger value="changes">Changes</TabsTrigger>
        </TabsList>
        <div className="flex items-center gap-1.5">
          <Select
            items={versions.map((v) => ({ value: v.version, label: versionLabel(v) }))}
            value={version}
            onValueChange={(v) => {
              const picked = versions.find((d) => d.version === v);
              if (!picked) return;
              if (dirty && !confirm("Discard your unsaved changes?")) return;
              setVersion(picked.version);
              setText(picked.text);
            }}
          >
            <SelectTrigger size="sm" aria-label="Draft version">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {versions.map((v) => (
                <SelectItem key={v.version} value={v.version}>
                  {versionLabel(v)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button size="sm" onClick={save} disabled={!dirty || saving}>
            <SaveIcon />
            {saving ? "Saving" : "Save"}
          </Button>
          <Button
            size="icon-sm"
            variant="outline"
            aria-label="Copy the letter"
            onClick={() => navigator.clipboard.writeText(text).then(() => toast.success("Copied."))}
          >
            <CopyIcon />
          </Button>
          <Button size="icon-sm" variant="outline" aria-label="Download as Markdown" onClick={download}>
            <DownloadIcon />
          </Button>
        </div>
      </div>
      {dirty && <p className="text-xs text-amber-700">Unsaved changes.</p>}
      <TabsContent value="preview">
        <Markdown text={text} onCite={onCite} />
      </TabsContent>
      <TabsContent value="edit">
        <Textarea
          aria-label="Appeal letter"
          value={text}
          onChange={(e) => setText(e.target.value)}
          className="min-h-[28rem] font-mono text-xs leading-5"
        />
        <p className="mt-1 text-xs text-muted-foreground">
          Keep citations like [plan-1.2]; they link to the plan section in Preview.
        </p>
      </TabsContent>
      <TabsContent value="changes">
        <Changes from={agent?.text ?? ""} to={text} />
      </TabsContent>
    </Tabs>
  );
}
